from __future__ import annotations

import argparse
import audioop
import json
import logging
import queue
import sys
import time
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model


MODEL_PATH = Path("models/vosk-model-small-ru-0.22")
VOSK_SAMPLE_RATE = 16_000
LOGGER_NAME = "micro.asr"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{self.formatTime(record, datefmt='%Y-%m-%d %H:%M:%S')} "
            f"{record.levelname:<7} {record.name} {record.getMessage()}"
        )
        fields = getattr(record, "fields", None)
        if fields:
            extras = " ".join(f"{key}={value}" for key, value in fields.items())
            if extras:
                base = f"{base} | {extras}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Распознавание речи с микрофона в реальном времени через Vosk."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=MODEL_PATH,
        help=f"Путь к модели Vosk. По умолчанию: {MODEL_PATH}",
    )
    parser.add_argument(
        "--samplerate",
        type=int,
        default=None,
        help=(
            "Частота дискретизации микрофона. "
            "По умолчанию берется из выбранного устройства."
        ),
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Имя или индекс устройства ввода sounddevice.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="Показать доступные аудиоустройства и выйти.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Уровень логирования. По умолчанию: INFO.",
    )
    parser.add_argument(
        "--json-logs",
        action="store_true",
        help="Выводить логи в JSON-формате.",
    )
    return parser.parse_args()


def configure_logging(log_level: str, json_logs: bool) -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else TextFormatter())

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(getattr(logging, log_level))
    logger.propagate = False
    logger.addHandler(handler)
    return logger


def log_event(
    logger: logging.Logger, level: int, message: str, **fields: object
) -> None:
    logger.log(level, message, extra={"fields": fields})


def print_devices(logger: logging.Logger) -> None:
    for index, device in enumerate(sd.query_devices()):
        default_mark = "*" if index == sd.default.device[0] else " "
        samplerate = int(device["default_samplerate"])
        device_line = (
            f"{default_mark} {index:>2} {device['name']} "
            f"({device['max_input_channels']} in, {device['max_output_channels']} out, "
            f"default {samplerate} Hz)"
        )
        print(device_line)
        log_event(
            logger,
            logging.INFO,
            "audio_device_detected",
            index=index,
            name=device["name"],
            input_channels=device["max_input_channels"],
            output_channels=device["max_output_channels"],
            default_samplerate=samplerate,
            is_default=index == sd.default.device[0],
        )


def parse_device(value: str | None) -> int | str | None:
    if value is None:
        return None
    if value.isdigit():
        return int(value)
    return value


def extract_text(payload: str) -> str:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    return (data.get("text") or data.get("partial") or "").strip()


def resolve_input_settings(
    device: int | str | None, samplerate: int | None
) -> tuple[int | str | None, int]:
    device_info = sd.query_devices(device, "input")
    resolved_samplerate = samplerate or int(device_info["default_samplerate"])
    return device, resolved_samplerate


def resample_audio(
    data: bytes, input_rate: int, output_rate: int, state: object | None
) -> tuple[bytes, object | None]:
    if input_rate == output_rate:
        return data, state
    converted, new_state = audioop.ratecv(data, 2, 1, input_rate, output_rate, state)
    return converted, new_state


def main() -> int:
    args = parse_args()
    args.device = parse_device(args.device)
    logger = configure_logging(args.log_level, args.json_logs)

    if args.list_devices:
        print_devices(logger)
        return 0

    model_path = args.model.expanduser().resolve()
    if not model_path.exists():
        log_event(
            logger,
            logging.ERROR,
            "model_not_found",
            model_path=str(model_path),
        )
        return 1

    try:
        args.device, args.samplerate = resolve_input_settings(
            args.device, args.samplerate
        )
    except Exception as exc:
        logger.exception("input_settings_resolution_failed")
        return 1

    audio_queue: queue.Queue[bytes] = queue.Queue()
    resample_state: object | None = None

    def audio_callback(indata, frames, time, status) -> None:
        if status:
            log_event(
                logger,
                logging.WARNING,
                "audio_callback_status",
                status=str(status),
            )
        audio_queue.put(bytes(indata))

    log_event(logger, logging.INFO, "model_loading_started", model_path=str(model_path))
    model = Model(str(model_path))
    recognizer = KaldiRecognizer(model, VOSK_SAMPLE_RATE)
    recognizer.SetWords(True)

    log_event(
        logger,
        logging.INFO,
        "recognition_started",
        device=args.device if args.device is not None else "default",
        microphone_samplerate=args.samplerate,
        vosk_samplerate=VOSK_SAMPLE_RATE,
    )
    print(
        "Распознавание запущено. "
        f"Устройство: {args.device if args.device is not None else 'default'}, "
        f"частота микрофона: {args.samplerate} Hz, "
        f"частота Vosk: {VOSK_SAMPLE_RATE} Hz. "
        "Говорите в выбранный микрофон. Для выхода нажмите Ctrl+C.",
        flush=True,
    )

    try:
        with sd.RawInputStream(
            samplerate=args.samplerate,
            blocksize=8_000,
            device=args.device,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while True:
                data = audio_queue.get()
                queue_depth = audio_queue.qsize()
                converted, resample_state = resample_audio(
                    data, args.samplerate, VOSK_SAMPLE_RATE, resample_state
                )
                final_started_at = time.perf_counter()
                if recognizer.AcceptWaveform(converted):
                    text = extract_text(recognizer.Result())
                    final_elapsed_ms = (time.perf_counter() - final_started_at) * 1000
                    if text:
                        print(text, flush=True)
                        log_event(
                            logger,
                            logging.INFO,
                            "final_transcript",
                            text=f'"{text}"',
                            processing_ms=round(final_elapsed_ms, 1),
                            queue_depth=queue_depth,
                        )
                else:
                    partial = extract_text(recognizer.PartialResult())
                    if partial:
                        log_event(
                            logger,
                            logging.DEBUG,
                            "partial_transcript",
                            text=partial,
                            queue_depth=queue_depth,
                        )
    except KeyboardInterrupt:
        log_event(logger, logging.INFO, "shutdown_requested")
        final_text = extract_text(recognizer.FinalResult())
        if final_text:
            print(final_text, flush=True)
            log_event(
                logger,
                logging.INFO,
                "final_transcript_flush",
                text=f'"{final_text}"',
            )
        return 0
    except Exception as exc:
        logger.exception("recognition_loop_failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
