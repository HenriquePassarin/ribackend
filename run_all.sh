#!/usr/bin/env bash
# FrutaScan — sobe o backend (FastAPI) e o app Flutter (macOS) com um único comando.
#
# Uso:
#   ./run_all.sh               # backend + app Flutter
#   ./run_all.sh backend       # só o backend (Swagger em http://127.0.0.1:8000/docs)
#   ./run_all.sh app           # só o app macOS (backend já rodando)
#   ./run_all.sh web           # backend + app no NAVEGADOR (Chrome) em http://localhost:3000
#
# Opções:
#   --update        faz `git pull` no clone do backend antes de subir
#   --reset         apaga o banco (fruits.db) e recria
#   --no-examples   não cadastra as frutas de exemplo (para cadastrar tudo ao vivo)
#
# Variáveis opcionais: BACKEND_DIR (pasta do clone do ribackend), PORT (padrão 8000),
#   WEB_PORT (padrão 3000 — precisa estar em CORS_ORIGINS do backend), WEB_DEVICE (padrão chrome;
#   use web-server para abrir em outro navegador, ex.: Safari, acessando http://localhost:3000)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_REPO_URL="https://github.com/alexdonay/ribackend.git"
# Onde está o backend: (1) BACKEND_DIR, (2) a pasta acima, se este front estiver dentro do repositório
# do backend (ex.: <repo>/frontend), (3) um clone em ./ribackend (criado automaticamente).
if [ -z "${BACKEND_DIR:-}" ]; then
  if [ -f "$ROOT/../backend/app/main.py" ]; then
    BACKEND_DIR="$(cd "$ROOT/.." && pwd)"
  else
    BACKEND_DIR="$ROOT/ribackend"
  fi
fi
PORT="${PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
WEB_DEVICE="${WEB_DEVICE:-chrome}"
API="http://127.0.0.1:${PORT}"

MODE="all"
RESET=0
UPDATE=0
NO_EXAMPLES=0
for arg in "$@"; do
  case "$arg" in
    backend|app|all|web) MODE="$arg" ;;
    --reset) RESET=1 ;;
    --update) UPDATE=1 ;;
    --no-examples) NO_EXAMPLES=1 ;;
    *) echo "Argumento desconhecido: $arg"; exit 1 ;;
  esac
done

log()  { printf '\n\033[1;32m▶ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

BACKEND_PID=""
VISION_KIND="stub"   # custom (modelo treinado/do .env) | reference (ImageNet) | stub
cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    printf '\nEncerrando o backend (pid %s)…\n' "$BACKEND_PID"
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

sha256_of() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }

env_get() { { grep -E "^$1=" .env 2>/dev/null || true; } | tail -1 | cut -d= -f2- | tr -d '\r'; }

set_env() { # set_env CHAVE VALOR  (reescreve a chave no .env, compatível com macOS/Linux)
  local key="$1" value="$2"
  { grep -v "^${key}=" .env || true; echo "${key}=${value}"; } > .env.tmp && mv .env.tmp .env
}

pick_python() {
  local c
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
      echo "$c"; return 0
    fi
  done
  return 1
}

download_checked() { # download_checked URL DESTINO SHA256
  local url="$1" dest="$2" sha="$3"
  if [ -f "$dest" ] && [ "$(sha256_of "$dest")" = "$sha" ]; then return 0; fi
  curl -fL --retry 2 -o "$dest" "$url" || return 1
  [ "$(sha256_of "$dest")" = "$sha" ] || { rm -f "$dest"; return 1; }
}

# Normalização ImageNet (RGB, 0-1, média/desvio por canal) — vale para o MobileNetV2 de
# referência e para o modelo treinado de 9 frutas. Exige backend com MODEL_INPUT_STD.
apply_imagenet_norm() {
  set_env VISION_PROVIDER opencv
  set_env MODEL_INPUT_SIZE 224
  set_env MODEL_INPUT_SCALE 0.00392156862745098
  set_env MODEL_INPUT_MEAN 0.485,0.456,0.406
  set_env MODEL_INPUT_STD 0.229,0.224,0.225
  set_env MODEL_SWAP_RB true
}

configure_vision() {
  local provider model labels
  provider="$(env_get VISION_PROVIDER)"
  model="$(env_get MODEL_PATH)"
  labels="$(env_get MODEL_LABELS_PATH)"

  # 1) O .env já aponta para um modelo próprio (ex.: o enviado pelo dev do backend): não mexe.
  if [ "$provider" = "opencv" ] && [ -n "$model" ]; then
    case "$model" in
      *mobilenetv2-7.onnx) ;;  # modelo de referência: tratado no passo 3 (reaplica a normalização correta)
      *)
        if [ -f "$model" ] && [ -f "$labels" ]; then
          VISION_KIND="custom"
          log "Usando o modelo configurado no .env: $model"
          return 0
        fi
        die "O .env aponta para '$model' e '$labels', mas esses arquivos não existem em $(pwd).
   Copie os dois arquivos do modelo (peça ao dev do backend) para $(pwd)/models/
   ou apague o .env para usar o modelo de referência."
        ;;
    esac
  fi

  # 2) Modelo treinado (baseline de 9 frutas) presente em models/
  if [ -f models/fruits-mobilenetv2-baseline.onnx ] && [ -f models/fruits-mobilenetv2-baseline.labels.txt ]; then
    log "Modelo treinado encontrado em models/ — ativando (9 frutas)"
    apply_imagenet_norm
    set_env MODEL_PATH models/fruits-mobilenetv2-baseline.onnx
    set_env MODEL_LABELS_PATH models/fruits-mobilenetv2-baseline.labels.txt
    set_env MODEL_OUTPUT_SOFTMAX true
    VISION_KIND="custom"
    return 0
  fi

  # 3) Modelo de referência (MobileNetV2 / ImageNet)
  log "Preparando o modelo de referência (MobileNetV2 / ImageNet)"
  mkdir -p models
  local ok=0
  if .venv/bin/python scripts/fetch_model.py --model mobilenetv2-7 >/dev/null 2>&1 \
     && [ -f models/mobilenetv2-7.onnx ] && [ -f models/ilsvrc2012_labels.txt ]; then
    ok=1
  else
    warn "Download pelo script falhou; tentando com curl…"
    if download_checked \
         "https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-7.onnx" \
         models/mobilenetv2-7.onnx \
         c1c513582d56afceff8516c73804e484c81c6a830712ab6d682253f4a3cd042f \
       && download_checked \
         "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/dnn/classification_classes_ILSVRC2012.txt" \
         models/ilsvrc2012_labels.txt \
         4eb3da435cf544e4a6f390f62c84cb9c9bb68cf8b14e97f8a063452382e5efd2; then
      ok=1
    fi
  fi

  if [ "$ok" = "1" ]; then
    log "Reconhecimento REAL com o modelo de referência (reconhece só espécies do ImageNet)"
    apply_imagenet_norm
    set_env MODEL_PATH models/mobilenetv2-7.onnx
    set_env MODEL_LABELS_PATH models/ilsvrc2012_labels.txt
    set_env MODEL_OUTPUT_SOFTMAX auto
    VISION_KIND="reference"
  else
    warn "Não consegui baixar o modelo. Usando o modo SIMULADO (stub): o app avisa na tela."
    set_env VISION_PROVIDER stub
    VISION_KIND="stub"
  fi
}

setup_backend() {
  command -v git >/dev/null 2>&1 || die "git não encontrado."
  if [ ! -f "$BACKEND_DIR/backend/app/main.py" ]; then
    log "Clonando o backend em $BACKEND_DIR"
    git clone "$BACKEND_REPO_URL" "$BACKEND_DIR"
  elif [ "$UPDATE" = "1" ]; then
    log "Atualizando o backend (git pull)"
    git -C "$BACKEND_DIR" pull --ff-only || warn "Não foi possível atualizar (há alterações locais no clone?)."
  fi
  cd "$BACKEND_DIR/backend"

  grep -q "model_input_std" app/core/config.py \
    || die "Seu clone do backend está desatualizado (falta MODEL_INPUT_STD). Rode: ./run_all.sh --update"

  local py
  py="$(pick_python)" || die "Python 3.11+ não encontrado. Instale com: brew install python@3.12"

  if [ ! -d .venv ]; then
    log "Criando ambiente virtual ($($py --version))"
    "$py" -m venv .venv
  fi
  log "Instalando dependências do backend (pode demorar na primeira vez)"
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r requirements.txt

  [ -f .env ] || cp .env.example .env

  if [ "$RESET" = "1" ]; then
    warn "Removendo banco de dados anterior (fruits.db)"
    rm -f fruits.db
  fi

  configure_vision

  if [ "$VISION_KIND" != "custom" ]; then
    log "Carregando frutas de exemplo (seed do backend)"
    .venv/bin/python scripts/seed_dev_data.py
  fi
}

register_examples() {
  [ "$VISION_KIND" = "custom" ] || return 0
  [ "$NO_EXAMPLES" = "0" ] || return 0
  cd "$BACKEND_DIR/backend"
  local labels
  labels="$(env_get MODEL_LABELS_PATH)"
  case "$labels" in /*) ;; *) labels="$BACKEND_DIR/backend/$labels" ;; esac
  log "Cadastrando frutas de exemplo com os rótulos do modelo"
  .venv/bin/python "$ROOT/register_examples.py" "$API" "$labels" || warn "Algumas frutas de exemplo não foram cadastradas."
}

start_backend() {
  cd "$BACKEND_DIR/backend"
  if curl -fs "$API/health" >/dev/null 2>&1; then
    warn "Já existe um backend respondendo em $API — vou reaproveitá-lo."
    warn "Se você mudou o .env/modelo/código, pare o antigo antes:  lsof -ti:${PORT} | xargs kill"
    return 0
  fi
  log "Iniciando o backend em $API"
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" > "$ROOT/backend.log" 2>&1 &
  BACKEND_PID=$!
  local i
  for i in $(seq 1 40); do
    if curl -fs "$API/health" >/dev/null 2>&1; then
      echo "Backend no ar. Swagger: $API/docs   (log: $ROOT/backend.log)"
      return 0
    fi
    kill -0 "$BACKEND_PID" 2>/dev/null || { tail -n 30 "$ROOT/backend.log"; die "O backend encerrou ao iniciar."; }
    sleep 1
  done
  tail -n 30 "$ROOT/backend.log"
  die "O backend não respondeu em 40s."
}

patch_entitlements() { # permite rede e seleção de arquivos no sandbox do macOS (só altera se faltar)
  local file="$1" key current
  for key in com.apple.security.network.client com.apple.security.files.user-selected.read-only; do
    current="$(/usr/libexec/PlistBuddy -c "Print :${key}" "$file" 2>/dev/null || true)"
    if [ "$current" != "true" ]; then
      /usr/libexec/PlistBuddy -c "Add :${key} bool true" "$file" 2>/dev/null \
        || /usr/libexec/PlistBuddy -c "Set :${key} true" "$file"
    fi
  done
}

brand_web() { # troca o nome padrão "fruta_app" por "FrutaScan" no título/manifest da web
  local f
  for f in "$ROOT/web/index.html" "$ROOT/web/manifest.json"; do
    if [ -f "$f" ]; then
      sed 's/fruta_app/FrutaScan/g' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
    fi
  done
}

ensure_platform() { # ensure_platform macos|web  — gera a pasta da plataforma com o próprio Flutter
  local platform="$1" tmp
  [ -d "$ROOT/$platform" ] && return 0
  log "Gerando a plataforma $platform do Flutter"
  tmp="$(mktemp -d)"
  flutter create --platforms="$platform" --project-name fruta_app "$tmp/fruta_app" >/dev/null
  cp -R "$tmp/fruta_app/$platform" "$ROOT/$platform"
  rm -rf "$tmp"
  if [ "$platform" = "web" ]; then brand_web; fi
}

setup_flutter() { # setup_flutter [macos|web]
  local platform="${1:-macos}"
  command -v flutter >/dev/null 2>&1 || die "Flutter não encontrado no PATH. Veja https://docs.flutter.dev/get-started/install/macos"
  cd "$ROOT"
  ensure_platform "$platform"
  if [ "$platform" = "macos" ]; then
    patch_entitlements macos/Runner/DebugProfile.entitlements
    patch_entitlements macos/Runner/Release.entitlements
  fi
  log "Baixando pacotes do Flutter"
  flutter pub get
}

# No navegador o backend precisa liberar a origem da página (CORS_ORIGINS).
ensure_web_cors() {
  cd "$BACKEND_DIR/backend"
  local origin="http://localhost:${WEB_PORT}" origins
  origins="$(env_get CORS_ORIGINS)"
  case ",${origins}," in *",${origin},"*) return 0 ;; esac
  warn "Liberando ${origin} no CORS do backend (necessário para rodar no navegador)"
  if [ -n "$origins" ]; then set_env CORS_ORIGINS "${origins},${origin}"; else set_env CORS_ORIGINS "${origin}"; fi
}

case "$MODE" in
  backend)
    setup_backend
    start_backend
    register_examples
    echo; echo "Backend rodando. Pressione Ctrl+C para encerrar."
    if [ -n "$BACKEND_PID" ]; then wait "$BACKEND_PID"; fi
    ;;
  app)
    setup_flutter
    log "Abrindo o app (macOS)"
    flutter run -d macos
    ;;
  web)
    setup_backend
    ensure_web_cors
    start_backend
    register_examples
    setup_flutter web
    log "Abrindo o app no navegador em http://localhost:${WEB_PORT}"
    cd "$ROOT"
    flutter run -d "$WEB_DEVICE" --web-port="$WEB_PORT"
    ;;
  all)
    setup_backend
    start_backend
    register_examples
    setup_flutter
    log "Abrindo o app (macOS) — a primeira compilação demora alguns minutos"
    cd "$ROOT"
    flutter run -d macos
    ;;
esac
