# Micro

Простой проект на Python 3 для распознавания русской речи с микрофона в реальном времени через Vosk.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Если `sounddevice` не запускается, установите системный PortAudio:

```bash
sudo apt install portaudio19-dev
```

## Запуск

```bash
python3 main.py
```

Полезные опции:

```bash
python3 main.py --list-devices
python3 main.py --device 1
python3 main.py --device 1 --samplerate 48000
python3 main.py --log-level DEBUG
python3 main.py --json-logs
```

Модель по умолчанию берется из `models/vosk-model-small-ru-0.22`.
Если `--samplerate` не указан, программа использует `default_samplerate` выбранного микрофона.
Входной аудиопоток автоматически ресемплится в `16000 Hz` перед передачей в Vosk.
Операционные события пишутся через `logging`: по умолчанию в текстовом формате, а для контейнеров и сборщиков логов доступен JSON через `--json-logs`.

## Docker

Сборка образа:

```bash
docker build -t micro-vosk .
```

Показать аудиоустройства из контейнера:

```bash
docker run --rm -it --device /dev/snd micro-vosk --list-devices
```

Запуск распознавания:

```bash
docker run --rm -it --device /dev/snd micro-vosk
docker run --rm -it --device /dev/snd micro-vosk --device 1
```

Контейнер рассчитан на Linux с ALSA. Для доступа к микрофону пробрасывается `/dev/snd` с хоста.
