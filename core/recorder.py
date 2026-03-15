"""
recorder.py — кросс-платформенная запись аудио.

Windows:  микрофон (sounddevice) + системный звук (PyAudioWPatch/WASAPI)
macOS:    микрофон (sounddevice), системный звук через BlackHole/Soundflower
Linux:    микрофон (sounddevice), системный звук через PulseAudio/PipeWire

PyAudioWPatch (WASAPI loopback) — только Windows, импортируется лениво.
"""
import sys
import threading
import wave
import numpy as np
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

# PyAudioWPatch — только Windows
PYAUDIO_AVAILABLE = False
if sys.platform == "win32":
    try:
        import pyaudiowpatch as pyaudio
        PYAUDIO_AVAILABLE = True
    except ImportError:
        pass

import sounddevice as sd

AUDIO_DIR   = Path.home() / ".lesson_recorder" / "audio"
SAMPLE_RATE = 16000
CHANNELS    = 1
CHUNK       = 1024


def get_audio_path(lesson_id: int) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    return AUDIO_DIR / f"lesson_{lesson_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"


def get_input_devices() -> list[dict]:
    """Возвращает список входных аудиоустройств (кросс-платформа)."""
    devices = []
    try:
        device_list = sd.query_devices()
        for i, dev in enumerate(device_list):
            if dev.get("max_input_channels", 0) > 0:
                devices.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "samplerate": int(dev["default_samplerate"]),
                })
    except Exception:
        pass
    return devices


def get_system_audio_hint() -> str:
    """
    Возвращает подсказку о том, как включить запись системного звука
    на текущей платформе.
    """
    if sys.platform == "win32":
        return ""   # PyAudioWPatch работает автоматически
    elif sys.platform == "darwin":
        return (
            "Для записи системного звука на macOS установи BlackHole:\n"
            "  brew install blackhole-2ch\n"
            "Затем в System Preferences → Sound → Output выбери BlackHole,\n"
            "а в приложении выбери BlackHole как источник микрофона."
        )
    else:
        return (
            "Для записи системного звука на Linux:\n"
            "  PulseAudio: выбери 'Monitor of ...' в списке устройств\n"
            "  PipeWire:   используй pw-loopback"
        )


class Recorder(QThread):
    level_updated      = pyqtSignal(float)   # 0.0 – 1.0
    error_occurred     = pyqtSignal(str)
    finished_recording = pyqtSignal(str)     # path

    def __init__(self, source: str, output_path: str, mic_device_index: int = None):
        super().__init__()
        self.source           = source   # "mic" | "system" | "both"
        self.output_path      = output_path
        self.mic_device_index = mic_device_index
        self._stop_event      = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            if self.source == "mic":
                self._record_mic_only()
            elif self.source == "system":
                self._record_system()
            else:
                self._record_both()
        except Exception as e:
            self.error_occurred.emit(str(e))

    # ── Microphone (sounddevice — все платформы) ──────────────────────────────

    def _record_mic_only(self):
        frames = []
        kwargs = dict(samplerate=SAMPLE_RATE, channels=CHANNELS,
                      dtype="int16", blocksize=CHUNK)
        if self.mic_device_index is not None:
            kwargs["device"] = self.mic_device_index
        with sd.InputStream(**kwargs) as stream:
            while not self._stop_event.is_set():
                data, _ = stream.read(CHUNK)
                frames.append(data.copy())
                self.level_updated.emit(float(np.abs(data).mean() / 32768.0))
        self._save_wav(frames, self.output_path)
        self.finished_recording.emit(self.output_path)

    # ── System audio ──────────────────────────────────────────────────────────

    def _record_system(self):
        if sys.platform == "win32":
            self._record_system_windows()
        else:
            # macOS/Linux: системный звук = просто устройство ввода
            # (пользователь должен выбрать BlackHole / Monitor устройство)
            self._record_mic_only()

    def _record_system_windows(self):
        """WASAPI loopback — только Windows через PyAudioWPatch."""
        if not PYAUDIO_AVAILABLE:
            self.error_occurred.emit(
                "PyAudioWPatch не установлен.\n"
                "pip install PyAudioWPatch"
            )
            return

        pa = pyaudio.PyAudio()
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = pa.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"])

            if not default_speakers.get("isLoopbackDevice", False):
                for i in range(pa.get_device_count()):
                    dev = pa.get_device_info_by_index(i)
                    if (dev.get("isLoopbackDevice", False) and
                            dev["name"] == default_speakers["name"] + " [Loopback]"):
                        default_speakers = dev
                        break

            n_ch      = max(int(default_speakers.get("maxInputChannels", 0)), 1)
            src_rate  = int(default_speakers["defaultSampleRate"])
            record_ch = min(n_ch, 2)

            stream = pa.open(
                format=pyaudio.paInt16,
                channels=record_ch,
                rate=src_rate,
                input=True,
                input_device_index=default_speakers["index"],
                frames_per_buffer=CHUNK,
            )
            frames = []
            while not self._stop_event.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                arr  = np.frombuffer(data, dtype=np.int16).copy()
                self.level_updated.emit(float(np.abs(arr).mean() / 32768.0))
                frames.append(arr)
            stream.stop_stream()
            stream.close()

            if not frames:
                self.error_occurred.emit("Системный звук: данные не получены")
                return

            audio = np.concatenate(frames)
            if record_ch > 1:
                rem = len(audio) % record_ch
                if rem:
                    audio = audio[:-rem]
                audio = audio.reshape(-1, record_ch).mean(axis=1).astype(np.int16)
            if src_rate != SAMPLE_RATE:
                audio = self._resample(audio, src_rate, SAMPLE_RATE)

            self._save_wav_array([audio], self.output_path)
            self.finished_recording.emit(self.output_path)
        finally:
            pa.terminate()

    # ── Both ──────────────────────────────────────────────────────────────────

    def _record_both(self):
        """
        Параллельная запись микрофона и системного звука.
        На macOS/Linux оба потока читают из sounddevice (разные устройства).
        """
        mic_frames = []
        sys_frames = []
        sys_done   = threading.Event()

        def mic_thread():
            kwargs = dict(samplerate=SAMPLE_RATE, channels=CHANNELS,
                          dtype="int16", blocksize=CHUNK)
            if self.mic_device_index is not None:
                kwargs["device"] = self.mic_device_index
            with sd.InputStream(**kwargs) as stream:
                while not self._stop_event.is_set():
                    data, _ = stream.read(CHUNK)
                    mic_frames.append(data.copy())
                    self.level_updated.emit(float(np.abs(data).mean() / 32768.0))

        def sys_thread_windows():
            if not PYAUDIO_AVAILABLE:
                sys_done.set()
                return
            try:
                pa = pyaudio.PyAudio()
                wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
                spk = pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                if not spk.get("isLoopbackDevice", False):
                    for i in range(pa.get_device_count()):
                        dev = pa.get_device_info_by_index(i)
                        if (dev.get("isLoopbackDevice", False) and
                                dev["name"] == spk["name"] + " [Loopback]"):
                            spk = dev
                            break
                src_rate  = int(spk["defaultSampleRate"])
                n_ch      = max(int(spk.get("maxInputChannels", 0)), 1)
                record_ch = min(n_ch, 2)
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=record_ch,
                    rate=src_rate,
                    input=True,
                    input_device_index=spk["index"],
                    frames_per_buffer=CHUNK,
                )
                local_frames = []
                while not self._stop_event.is_set():
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    arr  = np.frombuffer(data, dtype=np.int16).copy()
                    local_frames.append(arr)
                stream.stop_stream()
                stream.close()
                pa.terminate()
                if local_frames:
                    audio = np.concatenate(local_frames)
                    if record_ch > 1:
                        rem = len(audio) % record_ch
                        if rem:
                            audio = audio[:-rem]
                        audio = audio.reshape(-1, record_ch).mean(axis=1).astype(np.int16)
                    if src_rate != SAMPLE_RATE:
                        audio = self._resample(audio, src_rate, SAMPLE_RATE)
                    sys_frames.append(audio)
            except Exception:
                pass
            finally:
                sys_done.set()

        t_mic = threading.Thread(target=mic_thread, daemon=True)
        t_mic.start()

        if sys.platform == "win32":
            t_sys = threading.Thread(target=sys_thread_windows, daemon=True)
            t_sys.start()
        else:
            # macOS/Linux: нет автоматического loopback
            # "both" = просто запись микрофона (system loopback требует настройки)
            sys_done.set()

        t_mic.join()
        sys_done.wait(timeout=3)

        mic_audio = (np.concatenate([f.flatten() for f in mic_frames])
                     if mic_frames else np.zeros(0, dtype=np.int16))
        sys_audio = (np.concatenate(sys_frames)
                     if sys_frames else np.zeros(0, dtype=np.int16))

        if len(sys_audio) == 0:
            # Только микрофон
            self._save_wav(mic_frames, self.output_path)
        else:
            length = max(len(mic_audio), len(sys_audio))
            if len(mic_audio) < length:
                mic_audio = np.pad(mic_audio, (0, length - len(mic_audio)))
            if len(sys_audio) < length:
                sys_audio = np.pad(sys_audio, (0, length - len(sys_audio)))
            mixed = np.clip(
                mic_audio.astype(np.int32) + sys_audio.astype(np.int32),
                -32768, 32767,
            ).astype(np.int16)
            self._save_wav_array([mixed], self.output_path)

        self.finished_recording.emit(self.output_path)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(src_rate, dst_rate)
        return resample_poly(audio, dst_rate // g, src_rate // g).astype(np.int16)

    @staticmethod
    def _save_wav(frames, path: str):
        with wave.open(path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            for f in frames:
                wf.writeframes(f.tobytes())

    @staticmethod
    def _save_wav_array(arrays, path: str):
        audio = np.concatenate(arrays)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
