"""
视频翻译管线服务

流程:
  1. 提取视频音频 → 人声分离
  2. ASR 语音识别（获取带时间戳的片段）
  3. 逐句处理（可断点续传）:
     a. 翻译该句文本
     b. 从人声文件中按时间戳截取该句原始音频 → 作为克隆参考
     c. 语音克隆（用该句人声参考）
  4. 整体视频变速: video_pts = sum(gen_dur) / sum(seg_dur)
  5. 逐句 audio 微调: tempo = gen_dur / (seg_dur * video_pts)
  6. 拼接音频 + 混音 + 压制
"""
import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import torch

from app.services.asr_service import transcribe_audio
from app.services.clone_service import clone
from app.services.translate_service import translate_svc
from app.services.vocal_service import vocal

logger = logging.getLogger(__name__)

MAX_SEGMENT_SEC = 45
TRANSLATE_WORKERS = 5
REF_CLIP_MAX_SEC = 30

# 音频调速安全范围（优先用 audio rubberband，超出范围则由视频反向补偿）
SAFE_AUDIO_TEMPO_MIN = 0.70
SAFE_AUDIO_TEMPO_MAX = 1.30
# rubberband 硬限制（安全范围兜底）
AUDIO_TEMPO_HARD_MIN = 0.25
AUDIO_TEMPO_HARD_MAX = 4.00

# ── 管线阶段常量 ──────────────────────────────────────────────
STAGE_EXTRACT = "audio_extracted"
STAGE_SEPARATE = "vocal_separated"
STAGE_ASR = "asr_done"
STAGE_TRANSLATE = "translate_done"
STAGE_CLONE = "clone_done"
STAGE_VIDEO_SPED = "video_sped"
STAGE_AUDIO_SPED = "audio_sped"
STAGE_COMPLETED = "completed"


def _hash_path(path: str | Path) -> str:
    return hashlib.md5(str(Path(path).resolve()).encode()).hexdigest()[:16]


def _run_ffmpeg(cmd: list[str], desc: str = "") -> str:
    logger.info(f"ffmpeg: {desc}  {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg 失败 ({desc}): {e.stderr[-400:].strip()}") from e


def _audio_duration(path: str | Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _video_fps(path: str | Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        )
        fps_str = result.stdout.strip()
        if "/" in fps_str:
            num, den = fps_str.split("/")
            return float(num) / float(den)
        return float(fps_str)
    except Exception:
        return 30.0


def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(segments: list[dict], output_path: str | Path) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _srt_time(seg["start"])
        end = _srt_time(seg["end"])
        text = seg.get("translated", seg.get("text", ""))
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


class VideoTranslateService:

    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "voxa_vt"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ── CKPT helpers ───────────────────────────────────────────

    @staticmethod
    def _ckpt_path(tmp: Path) -> Path:
        return tmp / "progress.json"

    @staticmethod
    def _save_ckpt(tmp: Path, data: dict):
        try:
            VideoTranslateService._ckpt_path(tmp).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"CKPT 保存失败: {e}")

    @staticmethod
    def _load_ckpt(tmp: Path) -> dict:
        p = VideoTranslateService._ckpt_path(tmp)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    # ── 各阶段实现 ─────────────────────────────────────────────

    def _separate_vocals(self, audio_path: Path, tmp_dir: Path, model_name=None) -> dict[str, str]:
        """人声分离，>45s 的音频分段处理再拼接"""
        dur = _audio_duration(str(audio_path))
        if dur <= MAX_SEGMENT_SEC * 1.1:
            r = vocal.separate(str(audio_path), model_name=model_name)
            return {"vocals": r.get("vocals", ""), "accompaniment": r.get("accompaniment", "")}

        parts_dir = tmp_dir / "vocal_parts"
        parts_dir.mkdir(exist_ok=True)
        seg_count = int(dur // MAX_SEGMENT_SEC) + (1 if dur % MAX_SEGMENT_SEC > 0 else 0)
        vp, bp = [], []
        for i in range(seg_count):
            t0 = i * MAX_SEGMENT_SEC
            t1 = min((i + 1) * MAX_SEGMENT_SEC, dur)
            raw = parts_dir / f"part_{i:04d}.wav"
            _run_ffmpeg(["ffmpeg", "-y", "-i", str(audio_path), "-ss", str(t0), "-to", str(t1),
                         "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(raw)],
                        f"分段 {i + 1}/{seg_count}")
            try:
                r = vocal.separate(str(raw), model_name=model_name)
                if r.get("vocals"):
                    p = parts_dir / f"v_{i:04d}.wav"
                    shutil.copy2(r["vocals"], p)
                    vp.append(str(p))
                if r.get("accompaniment"):
                    p = parts_dir / f"b_{i:04d}.wav"
                    shutil.copy2(r["accompaniment"], p)
                    bp.append(str(p))
            except Exception as e:
                logger.warning(f"分段 {i + 1} 分离失败: {e}")

        if not vp:
            raise RuntimeError("人声分离失败：所有分段均无结果")

        mv = tmp_dir / "vocals_full.wav"
        mb = tmp_dir / "bgm_full.wav"
        if len(vp) == 1:
            shutil.copy2(vp[0], mv)
        else:
            lst = tmp_dir / "vl.txt"
            lst.write_text("\n".join(f"file '{p}'" for p in vp), encoding="utf-8")
            _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                         "-c", "copy", str(mv)], "拼接人声")

        if bp:
            if len(bp) == 1:
                shutil.copy2(bp[0], mb)
            else:
                lb = tmp_dir / "bl.txt"
                lb.write_text("\n".join(f"file '{p}'" for p in bp), encoding="utf-8")
                _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lb),
                             "-c", "copy", str(mb)], "拼接 BGM")
        else:
            _run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i",
                         f"anullsrc=r=16000:cl=mono", "-t", str(dur), str(mb)], "静音 BGM")

        return {"vocals": str(mv), "accompaniment": str(mb)}

    def _batch_translate(self, segments, src_lang, tgt_lang):
        """并发翻译，失败时保留原文"""
        def _one(seg):
            text = seg["text"].strip()
            for attempt in range(3):
                try:
                    r = translate_svc.translate(text=text, source=src_lang or "auto", target=tgt_lang)
                    seg["translated_text"] = r["text"].strip()
                    return seg
                except Exception:
                    if attempt < 2:
                        time.sleep(1)
            # 全部失败
            seg["translated_text"] = text
            seg["translation_failed"] = True
            return seg

        results = []
        with ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS) as ex:
            for fut in as_completed({ex.submit(_one, s): s for s in segments}):
                results.append(fut.result())
        results.sort(key=lambda s: s.get("id", 0) if isinstance(s.get("id"), (int, float)) else 0)
        return results

    def _clone_one(self, seg: dict, vocals_path: Path, clips_dir: Path, idx: int) -> dict | None:
        """克隆单个片段的语音，失败返回 None"""
        seg_id = seg.get("id", idx)
        trans_text = seg.get("translated", seg.get("original", "")).strip()
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", 0.0)
        seg_dur = max(seg_end - seg_start, 0.5)

        # 截取参考人声
        ref = clips_dir / f"seg_{idx:04d}_ref.wav"
        if not ref.exists():
            ref_dur = min(seg_dur, REF_CLIP_MAX_SEC)
            _run_ffmpeg(["ffmpeg", "-y", "-i", str(vocals_path),
                         "-ss", str(seg_start), "-t", str(ref_dur),
                         "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(ref)],
                        f"截取参考音频 段{seg_id}")

        clip = clips_dir / f"seg_{idx:04d}.wav"
        if not clip.exists():
            try:
                clone.generate(
                    text=trans_text,
                    reference_wav_path=str(ref),
                    output_path=str(clip),
                )
            except Exception as e:
                logger.error(f"克隆失败 段{seg_id}: {e}")
                return None

        gen_dur = max(_audio_duration(str(clip)), 0.05)
        return {
            "id": seg_id,
            "start": seg_start,
            "end": seg_end,
            "original": seg.get("original", "").strip(),
            "translated": trans_text,
            "clip": str(clip),
            "seg_dur": seg_dur,
            "gen_dur": gen_dur,
        }

    # ── 主管线 ─────────────────────────────────────────────────

    def translate(
        self,
        video_path,
        output_path=None,
        source_lang=None,
        target_lang="zh",
        model_name=None,
        keep_temp=False,
        progress_callback=None,
    ) -> dict:
        video_path = Path(video_path).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}_{target_lang}.mp4"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        tag = f"vt_{_hash_path(video_path)}"
        stages: dict = {}
        t_start = time.time()

        def prog(stage: str, pct: float, msg: str):
            logger.info(f"[{stage}] {pct:.0%} {msg}")
            if progress_callback:
                progress_callback(stage, pct, msg)

        if not keep_temp:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        tmp = self.temp_dir / tag
        tmp.mkdir(parents=True, exist_ok=True)

        # ── 加载 CKPT ──
        ckpt = self._load_ckpt(tmp)
        last_stage = ckpt.get("stage", "")
        logger.info(f"CKPT stage: '{last_stage}'")

        audio_raw = tmp / "audio_raw.wav"
        vocals_wav = tmp / "vocals.wav"
        bgm_wav = tmp / "bgm.wav"
        clips_dir = tmp / "clips"
        clips_dir.mkdir(exist_ok=True)
        srt_out = tmp / "translated.srt"
        final_audio = tmp / "final_audio.wav"
        sped_video = tmp / "video_sped.mp4"

        # ── Stage 1: 提取音频 ──
        if last_stage < STAGE_EXTRACT:
            prog("extract", 0.02, "提取音频")
            _run_ffmpeg(["ffmpeg", "-y", "-i", str(video_path), "-vn",
                         "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_raw)],
                        "提取音频")
            ckpt["stage"] = STAGE_EXTRACT
            self._save_ckpt(tmp, ckpt)

        # ── Stage 2: 人声分离 ──
        if last_stage < STAGE_SEPARATE:
            prog("separate", 0.06, "人声分离")
            sep = self._separate_vocals(audio_raw, tmp, model_name)
            if sep.get("vocals"):
                shutil.copy2(sep["vocals"], vocals_wav)
            if sep.get("accompaniment"):
                shutil.copy2(sep["accompaniment"], bgm_wav)
            vocal.unload()
            if not vocals_wav.exists():
                raise RuntimeError("人声分离失败：vocals 文件未生成")

            ckpt["stage"] = STAGE_SEPARATE
            self._save_ckpt(tmp, ckpt)

        # ── Stage 3: ASR ──
        if last_stage < STAGE_ASR:
            prog("asr", 0.14, "语音识别")
            asr_result = transcribe_audio(str(vocals_wav), language=source_lang)  
            asr_segs = asr_result.get("segments", [])
            torch.cuda.empty_cache()
            if not asr_segs:
                raise RuntimeError("ASR 无结果")

            ckpt["asr_segments"] = asr_segs
            ckpt["stage"] = STAGE_ASR
            self._save_ckpt(tmp, ckpt)
        else:
            asr_segs = ckpt.get("asr_segments", [])

        total = len(asr_segs)

        # ── Stage 4: 翻译 ──
        if last_stage < STAGE_TRANSLATE:
            prog("translate", 0.20, f"翻译 {total} 段")
            translated = self._batch_translate(asr_segs, source_lang, target_lang)
            translated.sort(key=lambda s: s.get("start", 0))
            processed = [
                {
                    "id": i,
                    "start": s["start"],
                    "end": s["end"],
                    "original": s["text"].strip(),
                    "translated": s.get("translated_text", s["text"].strip()),
                    "translation_failed": s.get("translation_failed", False),
                }
                for i, s in enumerate(translated)
            ]
            ckpt["segments"] = processed
            ckpt["stage"] = STAGE_TRANSLATE
            self._save_ckpt(tmp, ckpt)
            logger.info(f"翻译完成，{total} 段")
        else:
            processed = ckpt.get("segments", [])

        # ── Stage 5: 语音克隆 ──
        if last_stage < STAGE_CLONE:
            for idx in range(total):
                seg = processed[idx]
                # 已经克隆过就跳过
                if seg.get("clip") or seg.get("clone_error"):
                    continue

                base_pct = 0.28
                clone_range = 0.38  # 0.28 ~ 0.66
                pct = base_pct + clone_range * (idx / total)
                prog("clone", pct, f"克隆 {idx + 1}/{total}")

                r = self._clone_one(seg, vocals_wav, clips_dir, idx)
                if r:
                    processed[idx] = r
                else:
                    processed[idx]["clone_error"] = True
                    processed[idx]["clip"] = ""
                    processed[idx]["seg_dur"] = max(seg["end"] - seg["start"], 0.5)
                    processed[idx]["gen_dur"] = 0.0

                # 每处理一段就保存 CKPT
                ckpt["segments"] = processed
                self._save_ckpt(tmp, ckpt)
    
            ckpt["stage"] = STAGE_CLONE
            self._save_ckpt(tmp, ckpt)
            logger.info(f"克隆完成")
            clone.unload()
        else:
            processed = ckpt.get("segments", [])

        # 统计有效片段（克隆成功的）
        valid_segs = [s for s in processed if not s.get("clone_error") and s.get("clip")]
        if not valid_segs:
            raise RuntimeError("所有片段克隆均失败，无法继续")

        # ── Stage 6: 视频变速 ──
        # 策略：优先音频 rubberband，调速幅度过大时由视频反向补偿
        #   desired_tempo = gen_dur / seg_dur
        #   audio_tempo  = clamp(desired_tempo, SAFE_MIN, SAFE_MAX)
        #   video_factor = desired_tempo / audio_tempo   → 全局 video_pts
        weighted_vf = 0.0
        total_w = 0.0
        audio_tempos: list[float] = []  # 每个有效片段的 safe audio tempo
        for s in valid_segs:
            seg = s.get("seg_dur", 0)
            gen = s.get("gen_dur", 0)
            if seg <= 0:
                continue
            raw = gen / seg
            safe = max(SAFE_AUDIO_TEMPO_MIN, min(SAFE_AUDIO_TEMPO_MAX, raw))
            audio_tempos.append(safe)
            vf = raw / safe
            weighted_vf += seg * vf
            total_w += seg

        video_pts = weighted_vf / total_w if total_w > 0 else 1.0
        src_fps = _video_fps(str(video_path))
        logger.info(
            f"调速策略: video_pts={video_pts:.4f}, "
            f"audio_tempo_range=[{min(audio_tempos):.2f}~{max(audio_tempos):.2f}] "
            f"({len(audio_tempos)} 有效段)" if audio_tempos else "调速策略: 无有效段"
        )

        video_sped = (last_stage >= STAGE_VIDEO_SPED)
        if abs(video_pts - 1.0) > 0.02 and not video_sped:
            prog("video_speed", 0.70, f"视频变速 {video_pts:.3f}x")
            _run_ffmpeg(["ffmpeg", "-y", "-i", str(video_path),
                         "-vf", f"setpts={video_pts:.4f}*PTS,fps={src_fps:.0f}",
                         "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                         "-an", str(sped_video)],
                        f"setpts={video_pts:.4f}")

            # 调整所有片段的时间戳
            for s in processed:
                s["start"] = round(s["start"] * video_pts, 3)
                s["end"] = round(s["end"] * video_pts, 3)

            ckpt["segments"] = processed
            ckpt["stage"] = STAGE_VIDEO_SPED
            self._save_ckpt(tmp, ckpt)
            video_sped = True

        cur_video = sped_video if video_sped else video_path

        # ── Stage 7: 逐句 audio tempo 微调 ──
        if last_stage < STAGE_AUDIO_SPED:
            for idx in range(total):
                s = processed[idx]
                if s.get("clone_error") or not s.get("clip"):
                    continue
                clip = Path(s["clip"])
                if not clip.exists():
                    continue

                slot = s["end"] - s["start"]
                gen = s.get("gen_dur", 0)
                if slot <= 0 or gen <= 0:
                    continue

                tempo = gen / slot
                if abs(tempo - 1.0) > 0.03:
                    tempo_clamped = max(AUDIO_TEMPO_HARD_MIN, min(AUDIO_TEMPO_HARD_MAX, tempo))
                    sp = clips_dir / f"seg_{idx:04d}_sp.wav"
                    _run_ffmpeg(["ffmpeg", "-y", "-i", str(clip),
                                 "-filter:a",
                                 f"rubberband=tempo={tempo_clamped:.4f}:pitch=1.0:formant=preserved",
                                 str(sp)],
                                f"audio {idx} tempo={tempo_clamped:.2f}")
                    shutil.move(str(sp), str(clip))
                    logger.info(f"段{idx}: rubberband {tempo_clamped:.2f}x ({gen:.1f}s → {slot:.1f}s)")

            ckpt["stage"] = STAGE_AUDIO_SPED
            self._save_ckpt(tmp, ckpt)

        # ── Stage 8: 生成 SRT 字幕 ──
        _write_srt(processed, srt_out)

        # ── Stage 9: 拼接音频 ──
        prog("concat", 0.82, "拼接音频")
        from pydub import AudioSegment as AS

        base_s = _audio_duration(str(cur_video))
        if base_s <= 0:
            base_s = max((s.get("end", 0) for s in processed), default=5) + 2
        combined = AS.silent(duration=int(base_s * 1000))
        for s in processed:
            cp = s.get("clip", "")
            if not cp:
                continue
            cpath = Path(cp)
            if not cpath.exists():
                continue
            pos = int(s["start"] * 1000)
            sl = int((s["end"] - s["start"]) * 1000)
            try:
                cl = AS.from_file(cpath)
                if len(cl) > sl > 0:
                    cl = cl[:sl]
                combined = combined.overlay(cl, position=max(0, pos))
            except Exception as e:
                logger.warning(f"叠加 段{s.get('id')} 失败: {e}")
        combined.export(str(tmp / "audio_c.wav"), format="wav")

        # ── Stage 10: 混音 ──
        prog("mix", 0.90, "混音")
        if bgm_wav.exists():
            tv = AS.from_file(str(tmp / "audio_c.wav"))
            bg = AS.from_file(str(bgm_wav))
            if len(bg) < len(tv):
                bg = bg * ((len(tv) // len(bg)) + 1)
            # 混音策略：BGM 降 -6dB 保留背景感，克隆人声降 -3dB 留空间
            # 使 BGM 清晰可闻同时不覆盖人声
            mixed = tv
            mixed = mixed.overlay(bg[:len(mixed)] - 3)
            mixed.export(str(final_audio), format="wav")
        else:
            shutil.copy2(str(tmp / "audio_c.wav"), str(final_audio))

        # ── Stage 11: 压制 ──
        prog("render", 0.95, "压制")
        sf = str(srt_out).replace("\\", "/").replace(":", "\\\\:")
        _run_ffmpeg(["ffmpeg", "-y", "-i", str(cur_video), "-i", str(final_audio),
                     "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                     "-c:a", "aac", "-b:a", "192k",
                     "-vf", f"subtitles={sf}", "-map", "0:v:0", "-map", "1:a:0",
                     "-shortest", str(output_path)],
                    "压制")

        # ── 清理 ──
        ckpt["stage"] = STAGE_COMPLETED
        self._save_ckpt(tmp, ckpt)
        ckpt_f = self._ckpt_path(tmp)
        if ckpt_f.exists():
            ckpt_f.unlink()
        if not keep_temp:
            shutil.rmtree(tmp, ignore_errors=True)

        total_t = time.time() - t_start
        clone_ok = sum(1 for s in processed if s.get("clip") and not s.get("clone_error"))
        logger.info(f"完成: {output_path} ({total_t:.1f}s, 克隆成功 {clone_ok}/{total})")

        return {
            "output_video": str(output_path.resolve()),
            "srt_translated": str(srt_out),
            "stages": stages,
            "total_time": round(total_t, 2),
            "segments_count": total,
            "clone_ok": clone_ok,
        }


video_translate_service = VideoTranslateService()