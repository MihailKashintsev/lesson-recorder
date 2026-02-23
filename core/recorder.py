import threading
import wave
import numpy as np
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import pyaudiowpatch as pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

import sounddevice as sd


AUDIO_DIR = Path.home() / ".lesson_recorder" / "audio"
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024


def get_audio_path(lesson_id: int) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    return AUDIO_DIR / f"lesson_{lesson_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"


def get_input_devices() -> list[dict]:
    """Возвращает список входных аудиоустройств."""
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


class Recorder(QThread):
    level_updated = pyqtSignal(float)        # audio level 0.0 – 1.0
    error_occurred = pyqtSignal(str)
    finished_recording = pyqtSignal(str)     # path to saved file

    def __init__(self, source: str, output_path: str, mic_device_index: int = None):
        super().__init__()
        self.source = source                  # "mic" | "system" | "both"
        self.output_path = output_path
        self.mic_device_index = mic_device_index  # None = default
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            if self.source == "mic":
                self._record_mic_only()
            elif self.source == "system":
                self._record_system_only()
            else:
                self._record_both()
        except Exception as e:
            self.error_occurred.emit(str(e))

    # ── Microphone only (via sounddevice) ──────────────────────────────────
    def _record_mic_only(self):
        frames = []
        kwargs = dict(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK)
        if self.mic_device_index is not None:
            kwargs["device"] = self.mic_device_index
        with sd.InputStream(**kwargs) as stream:
            while not self._stop_event.is_set():
                data, _ = stream.read(CHUNK)
                frames.append(data.copy())
                level = np.abs(data).mean() / 32768.0
                self.level_updated.emit(float(level))
        self._save_wav(frames, self.output_path)
        self.finished_recording.emit(self.output_path)

    # ── System audio only (WASAPI loopback) ────────────────────────────────
    def _record_system_only(self):
        if not PYAUDIO_AVAILABLE:
            self.error_occurred.emit(
                "pyaudiowpatch не установлен. Системный звук недоступен."
            )
            return

        pa = pyaudio.PyAudio()
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = pa.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )
            if not default_speakers.get("isLoopbackDevice", False):
                for i in range(pa.get_device_count()):
                    dev = pa.get_device_info_by_index(i)
                    if (dev.get("isLoopbackDevice", False) and
                            dev["name"] == default_speakers["name"] + " [Loopback]"):
                        default_speakers = dev
                        break

            stream = pa.open(
                format=pyaudio.paInt16,
                channels=default_speakers.get("maxInputChannels", 2),
                rate=int(default_speakers["defaultSampleRate"]),
                input=True,
                input_device_index=default_speakers["index"],
                frames_per_buffer=CHUNK,
            )
            frames = []
            src_rate = int(default_speakers["defaultSampleRate"])
            while not self._stop_event.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                arr = np.frombuffer(data, dtype=np.int16)
                level = np.abs(arr).mean() / 32768.0
                self.level_updated.emit(float(level))
                frames.append(arr)
            stream.stop_stream()
            stream.close()

            audio = np.concatenate(frames)
            if default_speakers.get("maxInputChannels", 2) > 1:
                audio = audio.reshape(-1, default_speakers["maxInputChannels"])
                audio = audio.mean(axis=1).astype(np.int16)
            if src_rate != SAMPLE_RATE:
                audio = self._resample(audio, src_rate, SAMPLE_RATE)

            self._save_wav_array([audio], self.output_path)
            self.finished_recording.emit(self.output_path)
        finally:
            pa.terminate()

    # ── Both mic + system ──────────────────────────────────────────────────
    def _record_both(self):
        mic_frames = []
        sys_frames = []
        sys_done = threading.Event()

        def mic_thread():
            kwargs = dict(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK)
            if self.mic_device_index is not None:
                kwargs["device"] = self.mic_device_index
            with sd.InputStream(**kwargs) as stream:
                while not self._stop_event.is_set():
                    data, _ = stream.read(CHUNK)
                    mic_frames.append(data.copy())
                    level = np.abs(data).mean() / 32768.0
                    self.level_updated.emit(float(level))

        def sys_thread():
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
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=spk.get("maxInputChannels", 2),
                    rate=int(spk["defaultSampleRate"]),
                    input=True,
                    input_device_index=spk["index"],
                    frames_per_buffer=CHUNK,
                )
                src_rate = int(spk["defaultSampleRate"])
                n_ch = spk.get("maxInputChannels", 2)
                while not self._stop_event.is_set():
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    arr = np.frombuffer(data, dtype=np.int16)
                    if n_ch > 1:
                        arr = arr.reshape(-1, n_ch).mean(axis=1).astype(np.int16)
                    if src_rate != SAMPLE_RATE:
                        arr = self._resample(arr, src_rate, SAMPLE_RATE)
                    sys_frames.append(arr)
                stream.stop_stream()
                stream.close()
                pa.terminate()
            except Exception:
                pass
            finally:
                sys_done.set()

        t_mic = threading.Thread(target=mic_thread, daemon=True)
        t_sys = threading.Thread(target=sys_thread, daemon=True)
        t_mic.start()
        t_sys.start()
        t_mic.join()
        sys_done.wait(timeout=3)

        mic_audio = np.concatenate([f.flatten() for f in mic_frames]) if mic_frames else np.zeros(0, dtype=np.int16)
        sys_audio = np.concatenate(sys_frames) if sys_frames else np.zeros(0, dtype=np.int16)

        length = max(len(mic_audio), len(sys_audio))
        if len(mic_audio) < length:
            mic_audio = np.pad(mic_audio, (0, length - len(mic_audio)))
        if len(sys_audio) < length:
            sys_audio = np.pad(sys_audio, (0, length - len(sys_audio)))

        mixed = np.clip(mic_audio.astype(np.int32) + sys_audio.astype(np.int32),
                        -32768, 32767).astype(np.int16)
        self._save_wav_array([mixed], self.output_path)
        self.finished_recording.emit(self.output_path)

    # ── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(src_rate, dst_rate)
        resampled = resample_poly(audio, dst_rate // g, src_rate // g)
        return resampled.astype(np.int16)

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
