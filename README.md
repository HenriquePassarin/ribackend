# FrutaScan — front Flutter para o `ribackend`

App desktop (macOS) em Flutter que consome o backend FastAPI
<https://github.com/alexdonay/ribackend> (pasta `backend`):

- **Identificar fruta**: escolhe uma foto (JPG/PNG) → `POST /api/v1/recognitions` →
  mostra rótulo previsto, confiança e a fruta do cadastro (nome, código, preço) →
  o atendente **confirma**, **escolhe outra** (correção) ou **cadastra e confirma**
  → `POST /api/v1/recognitions/{id}/confirm`.
- **Catálogo**: lista, busca e filtra (`GET /api/v1/fruits`) e **cadastra** frutas
  (`POST /api/v1/fruits`), incluindo o `vision_label` que liga o modelo ao cadastro.
- Indicador de conexão (`GET /health`) e endereço do backend configurável (clique no card da barra lateral).

## Pré-requisitos (Mac)

- Flutter com suporte a macOS (`flutter doctor` sem erros em *macOS desktop*; precisa de Xcode)
- Python 3.11+ (`brew install python@3.12`)
- git e internet na primeira execução (clona o backend, instala dependências e baixa o modelo ONNX ~14 MB)

## Rodar tudo

```bash
cd fruta_app
./run_all.sh
```

O script clona o backend em `./ribackend`, cria a venv, instala as dependências, baixa o modelo,
carrega frutas de exemplo, sobe o backend em `http://127.0.0.1:8000`, gera a pasta `macos/`
(com as permissões de rede e de seleção de arquivo) e executa `flutter run -d macos`.
Ao fechar o app (Ctrl+C), o backend é encerrado.

Outras opções: `./run_all.sh backend` (só API, Swagger em `/docs`), `./run_all.sh app`
(só o app) e `./run_all.sh --reset` (recria o banco de exemplo).

## Sobre o reconhecimento

- Com o modelo baixado, o backend roda em modo **real** (`VISION_PROVIDER=opencv`, MobileNetV2/ImageNet).
  Ele reconhece espécies como `banana`, `orange`, `lemon`, `strawberry`, `pomegranate`, `fig`
  e `Granny Smith`; **não distingue variedades comerciais** e a confiança costuma ser baixa
  (por isso a confirmação humana é sempre exigida).
- Se o download falhar, o backend cai no modo **simulado** (`stub`) e o app mostra um aviso
  laranja em cada resultado.
- O backend não cria preços reais: as frutas de exemplo vêm com R$ 0,00. Cadastre frutas com
  preço pelo app durante a apresentação.

## Roteiro sugerido para a apresentação

1. Abrir **Catálogo** → mostrar frutas de exemplo → **Nova fruta** (ex.: Banana Prata, código
   `00002`, preço, rótulo `banana`).
2. Ir em **Identificar fruta** → escolher a foto de uma banana → **Identificar**.
3. Mostrar a previsão, a barra de confiança e a fruta vinda do cadastro → **Confirmar**.
4. Repetir com uma fruta sem cadastro → status "Sem correspondência" → **Cadastrar e confirmar**
   (o rótulo previsto já vem preenchido) ou **Selecionar fruta** para corrigir.

## Estrutura

```
lib/
  main.dart
  core/     api_client.dart · models.dart · app_state.dart · theme.dart
  screens/  shell.dart · recognize_screen.dart · catalog_screen.dart
  widgets/  common.dart · fruit_form_dialog.dart · fruit_picker_dialog.dart
run_all.sh
```
