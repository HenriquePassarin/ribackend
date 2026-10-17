# Backend — Identificação de frutas por visão computacional

API REST em Python + FastAPI que sugere a identificação de frutas e variedades comerciais
para apoiar o atendente de caixa. O sistema recebe uma imagem, consulta um componente de
visão computacional isolado, associa a classe prevista ao cadastro comercial do mercado e
devolve a sugestão com a confiança estimada e a necessidade de confirmação humana. O
atendente pode **confirmar** ou **corrigir** o resultado; a ação fica registrada.

## Aviso importante sobre o reconhecimento

Existem três modos, escolhidos por `VISION_PROVIDER`:

- **`opencv`** — classificador **ONNX real** executado com OpenCV (`cv2.dnn`), com
  decodificação real da imagem. É o modo de inferência de verdade; veja a seção
  [Reconhecimento real com OpenCV](#reconhecimento-real-com-opencv-onnx).
- **`stub`** (padrão) — **simulador de desenvolvimento** que deriva um rótulo
  determinístico do *hash* dos bytes da imagem. Ele **não** reconhece frutas, não foi
  avaliado em nenhum dataset e não deve ser usado em produção nem confundido com
  reconhecimento real (versão `development-stub-v0`, `is_simulated=True`, bloqueado em
  `APP_ENV=production`).
- **`disabled`** — o serviço de visão fica indisponível e a API responde 503 sem inventar
  resultado.

Nenhum preço, código comercial, dataset, métrica de acurácia ou integração com PDV foi
inventado neste projeto. Código e preço sempre vêm do cadastro. O modelo de referência
incluído (ImageNet) **não** distingue variedades comerciais: sem treinar em um dataset do
seu contexto, as previsões não são confiáveis para decisão de preço.

## Requisitos

- Python 3.11 ou superior (implementação verificada em **Python 3.12.3**).
- Windows, Linux ou macOS. Os comandos abaixo são para bash; há variações para Windows.

## Instalação e execução local

Fluxo de referência (bash / Linux / macOS / Git Bash):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt      # execução
python -m pip install -r requirements-dev.txt  # + testes (inclui o requirements.txt)
cp .env.example .env
uvicorn app.main:app --reload
```

Ativação do ambiente virtual no Windows:

| Shell | Comando |
| --- | --- |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Prompt de comando (cmd) | `.venv\Scripts\activate.bat` |
| Git Bash / MSYS | `source .venv/Scripts/activate` |

Sem ativar o ambiente, use o interpretador direto:
`.venv/Scripts/python.exe -m uvicorn app.main:app --reload` (Windows) ou
`.venv/bin/python -m uvicorn app.main:app --reload` (Linux/macOS).

Endereços locais:

| Recurso | URL |
| --- | --- |
| API | http://127.0.0.1:8000 |
| **Swagger UI** (documentação interativa, com “Try it out”) | http://127.0.0.1:8000/docs |
| ReDoc (mesma especificação, leitura alternativa) | http://127.0.0.1:8000/redoc |
| Especificação OpenAPI (JSON) | http://127.0.0.1:8000/openapi.json |
| Saúde | http://127.0.0.1:8000/health |

### Banco de dados

Não há migrações nesta versão. Com `DATABASE_URL=sqlite:///./fruits.db` e
`AUTO_CREATE_SCHEMA=true`, as tabelas são criadas na inicialização (arquivo local,
ignorado pelo Git). Para dados de exemplo **fictícios** de desenvolvimento:

```bash
python scripts/seed_dev_data.py
```

Antes de usar em produção: definir o banco real, desativar `AUTO_CREATE_SCHEMA` e adotar
migrações versionadas (por exemplo, Alembic).

O `scripts/seed_dev_data.py` adapta os rótulos ao provedor de visão ativo, porque
`vision_label` precisa casar exatamente com a classe prevista: com `VISION_PROVIDER=stub`
usa rótulos simulados; com `opencv` usa rótulos reais do modelo (por exemplo `banana`,
`orange`, `Granny Smith`). Os preços são gravados como `0.00` de propósito — nenhum preço
comercial é inventado.

## Testes

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest
```

Resultado real da última execução neste ambiente (Python 3.12.3, pytest 9.1.1):

```
collected 109 items
109 passed, 1 warning in 7.95s
```

Repetido em uma segunda `venv` limpa criada com `python -m pip install -r requirements-dev.txt`
(inclui `opencv-python 5.0.0` e `numpy 2.5.4`): `109 passed, 1 warning in 8.16s`.

Os 109 testes cobrem saúde, consulta/cadastro de frutas, upload e validação de imagens,
política de confiança, estados de reconhecimento, confirmação/correção, configuração, o
adaptador simulado e o adaptador OpenCV (decodificação, pré-processamento,
logits/softmax, mapeamento de rótulos e falhas do modelo). Nenhum teste unitário depende
de modelo real, rede ou dataset: a inferência é substituída por uma rede falsa
determinística e o banco é um SQLite em memória isolado por teste. Dois testes de
integração do adaptador OpenCV rodam apenas quando o modelo está presente em `models/` e
são pulados (com motivo explícito) caso contrário; verifique com
`pytest tests/test_opencv_recognizer.py -v`.

## Documentação interativa (Swagger UI / ReDoc)

A documentação é gerada pelo próprio FastAPI a partir dos schemas Pydantic, ou seja, o
mesmo contrato que valida as requisições é o que aparece no Swagger — não há documentação
escrita à mão que possa divergir do código.

```bash
uvicorn app.main:app --reload
# abra http://127.0.0.1:8000/docs
```

O que a documentação inclui:

- **Tags com descrição**: `health`, `fruits` e `recognitions`, explicando as regras de cada
  grupo (código/preço vêm do cadastro; `recognized` não é prova de acerto; imagens não são
  armazenadas).
- **Códigos de erro por rota**: cada endpoint anuncia só o que pode emitir. Por exemplo
  `POST /recognitions` documenta `400, 413, 415, 422, 500, 503, 504`; já
  `POST /recognitions/{id}/confirm` documenta apenas `400, 404, 422, 500`.
- **Significado de cada `error.code`** na descrição geral (`INVALID_IMAGE`,
  `IMAGE_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `MODEL_UNAVAILABLE`, `INFERENCE_TIMEOUT`,
  `INVALID_STATE`, entre outros).
- **Exemplos de requisição e resposta** em todos os schemas principais
  (`FruitCreate`, `RecognitionResponse`, `RecognitionConfirmRequest`, `ErrorResponse`…),
  marcados como ilustrativos — nenhum preço real de mercado.
- **Upload de imagem** com `multipart/form-data` (campo `file`) e `Try it out` habilitado,
  além de `displayRequestDuration` para ver a latência de cada chamada.

O Swagger sempre reflete a configuração em execução: com `VISION_PROVIDER=opencv`, o
“Try it out” do reconhecimento executa o modelo ONNX de verdade; com `stub`, executa o
simulador (os rótulos e a versão aparecem na resposta, o que evita confusão entre os modos).

## Reconhecimento real com OpenCV (ONNX)

O provedor `opencv` é a implementação de visão computacional de verdade:

1. `cv2.imdecode` decodifica a imagem (um arquivo que não é imagem válida falha aqui, e
   não apenas por assinatura de bytes).
2. `cv2.dnn.blobFromImage` faz redimensionamento, escala, média e troca de canais,
   todos configuráveis.
3. `cv2.dnn.readNetFromONNX` carrega o modelo **uma vez por configuração** (cache) e
   `net.forward()` roda a inferência, com `threading.Lock` porque `cv2.dnn.Net` não é
   seguro para uso concorrente na mesma instância.
4. A saída é convertida em probabilidades (softmax `auto`, `true` ou `false` — modelos da
   ONNX Model Zoo devolvem logits e foram verificados como logits) e o índice de maior
   probabilidade é traduzido pelo arquivo de rótulos.

### Como habilitar

```bash
python scripts/fetch_model.py --list                      # modelos registrados
python scripts/fetch_model.py --model mobilenetv2-7       # baixa e confere o SHA-256
```

`.env` correspondente (o script imprime este trecho):

```ini
VISION_PROVIDER=opencv
MODEL_PATH=models/mobilenetv2-7.onnx
MODEL_LABELS_PATH=models/ilsvrc2012_labels.txt
MODEL_INPUT_SIZE=224
MODEL_INPUT_SCALE=0.00392156862745098
MODEL_INPUT_MEAN=0,0,0
MODEL_SWAP_RB=false
MODEL_OUTPUT_SOFTMAX=auto
```

O vínculo com o cadastro continua por `fruit.vision_label`, que deve conter exatamente o
rótulo da classe do modelo (por exemplo `banana`). Sem correspondência, o status é
`no_catalog_match` e nenhum dado comercial é inventado.

### Verificação executada (resultados reais)

Servidor local com `VISION_PROVIDER=opencv` e o modelo MobileNetV2 do registro, sobre
fotos reais de frutas (imagens usadas só para verificação local e não versionadas):

| Caso | Resposta observada |
| --- | --- |
| Foto real de banana (fruta cadastrada com `vision_label=banana`) | `confirmation_required`, `label=banana`, `confidence=0.3484`, `fruit.code=00002` com preço vindo do cadastro |
| Foto real de maçã vermelha (sem classe correspondente) | `no_catalog_match`, `label=fig`, `confidence=0.3243`, `fruit=null` |
| `README.md` enviado como `image/png` | `400 INVALID_IMAGE` |

- `model_version` reportado: `mobilenetv2-7-c1c513582d56` (nome + SHA-256 do artefato), o
  que amarra cada previsão ao arquivo exato que a produziu.
- Latência medida nesta máquina (CPU, porta HTTP local, inclui upload e resposta): `0,76 s`
  na primeira requisição (carrega o modelo) e `0,14 s` aquecida. Medição isolada do
  `net.forward()` (224x224, n=30): média `38,7 ms`, p95 `64,8 ms`. **Não** é a latência do
  hardware alvo nem inclui câmera.

### O modelo de referência não é suficiente para o mercado

O MobileNetV2 do ImageNet-1k roda e classifica espécies, mas:

- **não distingue variedades comerciais** (Gala, Fuji, Red Delicious) — exatamente o caso
  em que códigos e preços diferem;
- **não cobre várias frutas de hortifruti**: sem uva, manga, tomate, melão, pera ou kiwi;
- a confiança fica baixa (~0,32–0,35 nas verificações acima) porque é um softmax sobre
  1000 classes de objetos, não de frutas — o que reforça a necessidade de
  `ALWAYS_REQUIRE_CONFIRMATION` e de calibrar `MIN_RECOGNITION_CONFIDENCE` com experimentos.

Para identificar variedades é necessário treinar um classificador em um dataset rotulado
(começando pelas frutas reais do mercado; `models/README.md` descreve o caminho,
incluindo o uso do Fruits-360 como ponto de partida público e a verificação de licença e
autorização). Exportar para ONNX e registrar URL + SHA-256 é suficiente para o adaptador
funcionar: nenhum código precisa mudar para trocar de modelo.

**Nenhuma métrica de acurácia, precisão, recall ou matriz de confusão é apresentada**, e
não há dataset embarcado neste repositório. As verificações acima são apenas checagens de
integração (poucas imagens), não avaliação de qualidade.

## Endpoints

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/health` | Verifica se a aplicação responde (`{"status": "ok"}`). |
| GET | `/api/v1/fruits` | Lista frutas; filtros `active`, `search`; paginação `limit`, `offset`. |
| POST | `/api/v1/fruits` | Cadastra fruta comercial (ver decisão D9). |
| GET | `/api/v1/fruits/{fruit_id}` | Busca fruta pelo identificador interno. |
| POST | `/api/v1/recognitions` | Recebe imagem (`multipart/form-data`, campo `file`) e sugere fruta. |
| POST | `/api/v1/recognitions/{recognition_id}/confirm` | Registra confirmação ou correção do atendente. |

Exemplo verificado de reconhecimento com o adaptador simulado
(`VISION_PROVIDER=stub`, adaptador **não** real):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/recognitions \
  -F "file=@fruta.png;type=image/png"
```

```json
{
  "recognition_id": "be56997b-ba19-416b-a459-b1c0ea6b082f",
  "status": "confirmation_required",
  "prediction": {
    "label": "apple_fuji",
    "confidence": 0.764,
    "model_version": "development-stub-v0"
  },
  "fruit": {
    "id": 2,
    "name": "Maçã Fuji (exemplo)",
    "code": "05678",
    "price_per_kg": "0.00",
    "unit": "kg"
  },
  "confirmation_required": true
}
```

Confirmação da sugestão (resposta real):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/recognitions/<recognition_id>/confirm \
  -H "Content-Type: application/json" -d '{"fruit_id": 2}'
```

```json
{
  "recognition_id": "c8a94ebb-38d7-4eba-824e-925996c2051c",
  "status": "confirmed",
  "fruit": {
    "id": 2,
    "name": "Maçã Fuji (exemplo)",
    "code": "05678",
    "price_per_kg": "0.00",
    "unit": "kg"
  },
  "confirmed_at": "2026-10-17T00:00:22.986666Z"
}
```

Confirmar a mesma tentativa novamente retorna `400 INVALID_STATE`.

### Estados do reconhecimento

| Status | Significado |
| --- | --- |
| `recognized` | Classe prevista e confiança acima do limiar. **Não é prova de acerto**; a política pode exigir confirmação. |
| `confirmation_required` | O atendente deve revisar o resultado (confiança abaixo do limiar ou ausente). |
| `unrecognized` | O modelo não devolveu classe aceitável; o atendente identifica manualmente. |
| `no_catalog_match` | Classe prevista sem fruta correspondente (ou correspondente inativa); `fruit` é `null`. |
| `confirmed` | O atendente confirmou a sugestão. |
| `corrected` | O atendente escolheu outra fruta. |
| `failed` | Falha técnica durante o processamento (registrada para auditoria, sem detalhes na resposta). |

Transições: `recognized`/`confirmation_required`/`unrecognized`/`no_catalog_match` →
`confirmed` ou `corrected`. `confirmed`, `corrected` e `failed` são terminais e não
aceitam nova confirmação (as regras estão em `app/models/recognition.py`, em
`CONFIRMABLE_STATUSES`/`FINAL_STATUSES`, e estão cobertas por testes).

## Padrão de erro

Todas as respostas de erro seguem o formato:

```json
{"error": {"code": "INVALID_IMAGE", "message": "O arquivo enviado não é uma imagem válida.", "details": null}}
```

| HTTP | Códigos | Uso |
| --- | --- | --- |
| 400 | `INVALID_IMAGE`, `EMPTY_IMAGE`, `FRUIT_INACTIVE`, `INVALID_STATE` | Requisição inválida ou incompatível com o estado atual. |
| 404 | `FRUIT_NOT_FOUND`, `RECOGNITION_NOT_FOUND`, `NOT_FOUND` | Recurso inexistente. |
| 409 | `DUPLICATE_FRUIT` | Código comercial ou rótulo já cadastrado. |
| 413 | `IMAGE_TOO_LARGE` | Imagem acima de `MAX_IMAGE_SIZE_MB`. |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Tipo declarado ou formato real não suportado. |
| 422 | `VALIDATION_ERROR` | Falha de validação dos dados de entrada. |
| 500 | `INTERNAL_ERROR` | Erro inesperado, sem stack trace nem detalhes internos. |
| 503 | `MODEL_UNAVAILABLE` | Modelo/dependência indisponível. |
| 504 | `INFERENCE_TIMEOUT` | Inferência excedeu `INFERENCE_TIMEOUT_SECONDS`. |

`429 Too Many Requests` não foi implementado (ver limitações).

## Configuração

Todas as configurações vêm de variáveis de ambiente (ou de um arquivo `.env`, não
versionado). O `.env.example` documenta os valores de exemplo e não contém segredos.

| Variável | Padrão | Observações |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `test` ou `production`. |
| `APP_NAME` / `APP_VERSION` | `fruit-recognition-api` / `0.1.0` | Metadados da aplicação. |
| `API_V1_PREFIX` | `/api/v1` | Prefixo das rotas de negócio. |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `text` | `LOG_FORMAT=json` para logs em JSON. |
| `DATABASE_URL` | `sqlite:///./fruits.db` | **Obrigatória por ambiente** ao trocar de banco (ver decisão D1). |
| `AUTO_CREATE_SCHEMA` | `true` | Conveniência de protótipo; desativar em produção. |
| `DB_ECHO` | `false` | Eco de SQL (apenas depuração). |
| `MAX_IMAGE_SIZE_MB` | `10` | Limite de upload; também limita a leitura em memória. |
| `INFERENCE_TIMEOUT_SECONDS` | `10` | Timeout da inferência; excedido → 504. |
| `MIN_RECOGNITION_CONFIDENCE` | `0.85` | Limiar de confiança (valor de exemplo, não validado em produção). |
| `ALWAYS_REQUIRE_CONFIRMATION` | `true` | Padrão seguro enquanto a política de produto não for definida. |
| `VISION_PROVIDER` | `stub` | `opencv` (ONNX real via cv2.dnn), `stub` (simulado) ou `disabled` (503). |
| `ALLOW_STUB_IN_PRODUCTION` | `false` | Exceção explícita e documentada para ambiente isolado de testes. |
| `MODEL_PATH` | vazio | Arquivo `.onnx`. **Obrigatório** (e precisa existir) quando `VISION_PROVIDER=opencv`. |
| `MODEL_LABELS_PATH` | vazio | Um rótulo por linha, na ordem das classes de saída. Obrigatório no modo `opencv`. |
| `MODEL_VERSION` | vazio | Identificação livre; se vazia, é derivada do nome + SHA-256 do arquivo. |
| `MODEL_INPUT_SIZE` | `224` | Lado da entrada quadrada do modelo. |
| `MODEL_INPUT_SCALE` | `1/255` | `1/255` para entrada em `[0,1]`; `1.0` para entrada em `[0,255]`. |
| `MODEL_INPUT_MEAN` | `0,0,0` | Média por canal (B,G,R) subtraída do blob. |
| `MODEL_SWAP_RB` | `false` | Troca de canais B/R quando o modelo espera RGB. |
| `MODEL_OUTPUT_SOFTMAX` | `auto` | `auto`, `true` ou `false` para tratar a saída do modelo. |
| `CORS_ORIGINS` | vazio | Origens separadas por vírgula; vazio desabilita CORS. |
| `FRUITS_DEFAULT_LIMIT` / `FRUITS_MAX_LIMIT` | `20` / `100` | Paginação; `limit` maior que o máximo é reduzido. |

A inicialização valida a configuração e falha com mensagem clara. Por exemplo,
`APP_ENV=production` com `VISION_PROVIDER=stub` levanta erro na inicialização, salvo se
`ALLOW_STUB_IN_PRODUCTION=true` for definido de forma explícita e documentada. Nenhum
valor secreto é registrado em log.

## Decisões técnicas tomadas

As decisões abaixo preencheram lacunas para desbloquear a primeira versão. Todas são
configuráveis ou isoladas atrás de interfaces.

- **D1 — Banco de dados: SQLite para protótipo, atrás de repositórios.** O banco definitivo
  é uma decisão pendente. O acesso a dados fica em `app/repositories/`, o SQLAlchemy 2.x é
  usado como ORM e a URL vem de `DATABASE_URL`. Recomendação para produção: PostgreSQL
  (`DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/frutas`, com o driver
  instalado), `AUTO_CREATE_SCHEMA=false` e migrações versionadas.
- **D2 — Sem migrações nesta versão.** `AUTO_CREATE_SCHEMA=true` cria as tabelas via
  metadados para protótipo/testes. Adotar Alembic antes de qualquer uso real.
- **D3 — Mapeamento classe do modelo → fruta cadastrada.** Implementado como campo
  explícito `fruit.vision_label` (único, opcional), consultado por
  `FruitRepository.get_by_vision_label`. Sem correspondência (ou correspondência inativa),
  o status é `no_catalog_match` e a resposta devolve `fruit: null`; o sistema nunca inventa
  nome, código ou preço. A alternativa de derivar o vínculo do código comercial foi
  descartada por acoplar o código do mercado aos rótulos do modelo.
- **D4 — Política de confiança e confirmação.** `recognized` exige confiança não nula e
  `>= MIN_RECOGNITION_CONFIDENCE`. Como a política de produto ainda não foi definida,
  `ALWAYS_REQUIRE_CONFIRMATION=true` é o padrão: mesmo acima do limiar, `recognized` pode
  vir com `confirmation_required=true`. Confiança nula nunca é tratada como confiança alta.
- **D5 — Interface de visão isolada.** `app/vision/base.py` define `Prediction` e o
  protocolo `FruitRecognizer` (`predict`, além de `supported_formats` e `is_simulated`,
  extensões usadas para validar upload e nunca apresentar o stub como real). A fábrica
  `app/vision/adapter.py` seleciona o adaptador por `VISION_PROVIDER`; `disabled` deixa o
  serviço indisponível (503) sem inventar resultados.
- **D6 — Stub de desenvolvimento determinístico.** `DevelopmentStubRecognizer` deriva
  rótulo e confiança de SHA-256 dos bytes da imagem (determinístico para os mesmos bytes),
  simula `unrecognized` em parte das entradas, marca `is_simulated=True` e usa a versão
  `development-stub-v0`. Só é ativado por configuração explícita e é **bloqueado** em
  `APP_ENV=production` sem exceção documentada.
- **D7 — Execução da inferência.** `predict` é síncrono e potencialmente bloqueante, então
  roda em thread separada (`anyio.to_thread.run_sync(..., abandon_on_cancel=True)`) sob
  `anyio.fail_after` com `INFERENCE_TIMEOUT_SECONDS`, sem bloquear o event loop do
  FastAPI. Exceder o tempo → `504`. Limitação: o thread bloqueante não é interrompido, é
  abandonado; um modelo real com cancelamento deve expor interface assíncrona própria.
- **D8 — Imagens não são armazenadas.** Não há coluna nem diretório de imagens, e os bytes
  não aparecem nos logs. A validação usa assinatura real do arquivo (`app/core/images.py`)
  e ignorar a extensão e o `Content-Type` declarados; o upload é lido em blocos para não
  carregar arquivos arbitrariamente grandes em memória.
- **D9 — `POST /api/v1/fruits` adicionado.** O contrato ilustrado define apenas consulta,
  mas o escopo inicial inclui cadastro de frutas; o endpoint foi incluído para permitir
  operar a API sem acesso direto ao banco. É uma extensão declarada, e não substitui uma
  futura integração com o cadastro oficial do mercado.
- **D10 — Erros padronizados e sem vazamento.** Handler único por tipo de exceção,
  `RequestValidationError` reduzido a `loc`/`msg`/`type`, e mensagens técnicas do adaptador
  (que podem conter caminhos internos) ficam apenas no log — o cliente recebe a mensagem
  padronizada. Falhas técnicas geram registro `failed` para auditoria.
- **D11 — Observabilidade mínima.** Logs de ciclo de vida, duração da inferência, resultado
  técnico e confirmações, com `X-Request-ID` (gerado ou repassado) correlacionando a
  requisição. `LOG_FORMAT=json` disponível. Métricas externas/Prometheus não foram
  implementadas por não haver ambiente de implantação definido.
- **D12 — CORS desabilitado por padrão** e restrito às origens de `CORS_ORIGINS` quando
  configurado; sem credenciais e limitado a `GET`/`POST`/`OPTIONS`.
- **D13 — Inference real com OpenCV (`cv2.dnn`) e modelo ONNX agnóstico.** O adaptador
  (`app/vision/opencv_classifier.py`) não conhece o modelo: recebe `MODEL_PATH`,
  `MODEL_LABELS_PATH` e os parâmetros de pré-processamento. Essa escolha permite trocar de
  modelo (inclusive um treinado no dataset do mercado) sem alterar rotas, serviços ou
  testes. O modelo carregado é cacheado por configuração e serializado por `Lock`.
  `MODEL_OUTPUT_SOFTMAX=auto` trata modelos que devolvem logits (caso dos artefatos da ONNX
  Model Zoo) sem exigir que o operador saiba disso.
- **D14 — Modelo de referência: MobileNetV2 (ImageNet-1k) apenas para integração.**
  Escolhido por ser um ONNX público pequeno (~14 MB), com SHA-256 verificável, que roda em
  CPU no `cv2.dnn` e cobre algumas espécies de fruta. Foi **rejeitado como solução final**
  por não distinguir variedades comerciais e não cobrir parte do hortifruti; a decisão
  sobre o modelo definitivo continua pendente (ver decisão 4) e depende de dataset real.

## Decisões ainda pendentes

Estas perguntas da especificação **não** foram respondidas nesta versão; nenhuma solução
inventada foi assumida como fato.

1. Qual banco de dados será utilizado? (o projeto usa SQLite apenas como protótipo)
2. O mercado já possui cadastro de frutas e códigos que possa ser consultado?
3. O sistema será integrado ao PDV ou funcionará inicialmente de forma independente?
4. Qual modelo de visão computacional será usado? (a integração `VISION_PROVIDER=opencv`
   já executa modelos ONNX reais; falta escolher/treinar o modelo definitivo, porque o de
   referência não distingue variedades)
5. O modelo identificará espécies, variedades comerciais ou ambas?
6. A câmera enviará imagens isoladas ou haverá vídeo em tempo real? (hoje: imagem isolada
   por requisição)
7. O processamento ocorrerá na máquina do caixa, em um servidor local ou na nuvem?
8. As imagens serão armazenadas para avaliação e melhoria do dataset? (hoje: não)
9. Haverá autenticação? Qual sistema será responsável por ela? (hoje: **não há
   autenticação**)
10. Qual latência é aceitável para o fluxo do caixa?
11. Quais unidades comerciais e regras de preço existem no cadastro real? (o campo `unit` é
    texto livre, padrão `kg`)
12. Qual política definirá quando uma sugestão pode ser exibida e quando a confirmação
    humana será obrigatória? (hoje: `ALWAYS_REQUIRE_CONFIRMATION=true`)

## Limitações conhecidas

- **Nenhum dataset de avaliação.** Existe integração real com OpenCV/ONNX, mas nenhum
  modelo foi treinado nem avaliado; portanto não há métrica de acurácia, precisão, recall
  ou matriz de confusão para relatar.
- **Sem treinamento.** `scripts/fetch_model.py` apenas baixa artefatos publicados com
  verificação de hash; não há código de treino, dataset ou conversão de modelos neste
  repositório.
- **Modelo de referência limitado**: ImageNet-1k só cobre algumas espécies de fruta e não
  distingue variedades (ver seção do OpenCV).
- **Inferência serializada por processo** no modo `opencv` (`threading.Lock` sobre a mesma
  instância de `cv2.dnn.Net`): requisições concorrentes esperam na fila. Para escala,
  considerar múltiplos workers, `cv2.dnn` com backend otimizado ou `onnxruntime`.
- **Modelo é recarregado na próxima requisição** se o carregamento falhar (o cache só
  guarda construções bem-sucedidas); o erro é reportado como `503 MODEL_UNAVAILABLE`.
- **Backend de execução do OpenCV não configurado**: usa o padrão de CPU; CUDA/OpenVINO
  não foram testados.
- **Sem autenticação** e sem limite de requisições (`429`). A API não deve ser exposta fora
  de um ambiente local controlado antes de definir autenticação (`APP_ENV=production` com
  stub é bloqueado, mas isso não substitui autenticação).
- **Sem migrações** e sem política de retenção/descarte (não há imagens armazenadas).
- **Timeout não interrompe o thread** de inferência: ele é abandonado (ver D7).
- **Validação de imagem é estrutural** (assinatura PNG/JPEG por padrão): não decodifica a
  imagem. Formatos suportados hoje: PNG e JPEG.
- **Busca de frutas** é case-insensitive para caracteres ASCII; a comparação de caracteres
  acentuados depende da *collation* do banco (limitação do SQLite, resolvida ao adotar
  PostgreSQL com a collation adequada).
- **Dinheiro não usa ponto flutuante binário**: preços são `Numeric(12,2)` no banco e
  serializados como string (`"8.99"`) para preservar a precisão decimal.
- **Adaptador é cacheado por processo** (`lru_cache`): trocar `MODEL_PATH`/`MODEL_VERSION`
  exige reinício do processo.
- Aviso de dependência: `starlette.testclient` sinaliza depreciação do uso de `httpx` com
  `httpx2` nesta versão; é um aviso da biblioteca de testes, não do código da aplicação.

## Próximos passos para integrar um modelo real

1. Escolher/treinar o modelo definitivo e definir formato/dimensões de entrada,
   pré-processamento e hardware alvo. A execução de inferência já está pronta em
   `app/vision/opencv_classifier.py` (`cv2.dnn`, ONNX); para outro framework, criar
   `app/vision/<modelo>.py` implementando pelo menos `predict` e registrá-lo em
   `_PROVIDER_FACTORIES` (`app/vision/adapter.py`).
2. Definir como cada classe do modelo é associada ao cadastro (`vision_label`) e registrar
   o dataset usado, com origem e autorização das imagens.
4. Definir o significado da confiança devolvida e calibrar `MIN_RECOGNITION_CONFIDENCE` com
   um dataset representativo do ambiente real — sem experimentos, o limiar atual continua
   sendo apenas um valor de exemplo.
5. Medir latência (média e percentis) e revisar `INFERENCE_TIMEOUT_SECONDS` e a estratégia
   de execução (thread vs. processo vs. fila).
6. Documentar o dataset e a avaliação conforme a seção 10 da especificação: origem e
   autorização das imagens, quantidade por variedade, condições de captura, critérios de
   rotulagem, separação treino/validação/teste sem vazamento, classes indistinguíveis,
   versão do dataset, precisão/recall/F1 por variedade, matriz de confusão, taxa de não
   reconhecimento, taxa de correções dos atendentes e latência ponta a ponta.
7. Definir o procedimento de atualização e reversão do modelo (versionamento de artefatos,
   `MODEL_VERSION`, migração de rótulos e *rollback*).
8. Substituir o SQLite, ativar migrações e definir autenticação antes de qualquer exposição
   real.

## Estrutura de diretórios

```
backend/
├── app/
│   ├── main.py                      # fábrica da aplicação, middleware e handlers de erro
│   ├── api/
│   │   ├── router.py                # agrega as rotas sob /api/v1
│   │   ├── dependencies.py          # injeção de dependências (banco, serviços, adaptador)
│   │   ├── uploads.py               # leitura de upload com limite de tamanho
│   │   └── routes/{health,fruits,recognitions}.py
│   ├── core/{config,errors,logging,database,images}.py
│   ├── schemas/{fruit,recognition,errors,health}.py
│   ├── models/{base,fruit,recognition}.py
│   ├── repositories/{fruit_repository,recognition_repository}.py
│   ├── services/{fruit_service,recognition_service}.py
│   └── vision/{base,adapter,development_stub,opencv_classifier}.py
├── models/README.md                 # registro do modelo; binários não versionados
├── scripts/
│   ├── fetch_model.py               # baixa/verifica modelo ONNX (SHA-256)
│   └── seed_dev_data.py             # dados de exemplo FICTÍCIOS
├── tests/                           # 109 testes (pytest)
├── .env.example  .gitignore  pyproject.toml
├── requirements.txt  requirements-dev.txt
└── README.md
```

## Critérios de aceite — evidência

| Critério | Evidência |
| --- | --- |
| Aplicação FastAPI inicia conforme o README | Verificado com `uvicorn app.main:app` (log de inicialização e `/health` respondendo). |
| Documentação OpenAPI disponível | `GET /openapi.json` com 6 operações, 3 tags com descrição, códigos de erro por rota e 10 schemas com exemplos; `GET /docs` (Swagger UI) e `GET /redoc` respondendo 200 (verificado por HTTP). |
| Endpoint de saúde responde | `GET /health` → `200 {"status":"ok"}`. |
| Cadastro de frutas consultável | `GET /api/v1/fruits` com filtros e paginação; coberto por 17 testes. |
| Contratos validados | Pydantic nos schemas + testes de 422 para payloads inválidos. |
| Aceita imagens válidas e rejeita inválidas/excessivas | Testes e verificação HTTP: 400 `INVALID_IMAGE`/`EMPTY_IMAGE`, 413 `IMAGE_TOO_LARGE`, 415 `UNSUPPORTED_MEDIA_TYPE`. |
| Visão isolada por interface | `FruitRecognizer` + fábrica por configuração; testes substituem o adaptador. |
| Reconhecimento, falta de correspondência e falha diferenciados | Estados `recognized`/`confirmation_required`/`unrecognized`/`no_catalog_match`/`failed` cobertos por testes. |
| Confiança não tratada como garantia | `confirmation_required=true` mesmo com confiança acima do limiar (teste dedicado). |
| Atendente confirma ou corrige | `POST /recognitions/{id}/confirm` → `confirmed`/`corrected` (verificado via HTTP). |
| Código e preço vêm do cadastro | Resposta de reconhecimento replica o cadastro; teste garante que a confirmação não altera cadastro/preço. |
| Erros padronizados | Formato único `{"error": {...}}` e testes de ausência de stack trace. |
| Configurações externas | `Settings` por variáveis de ambiente, validado na inicialização. |
| Testes automatizados críticos passam | `79 passed` (também em `venv` limpa criada de `requirements-dev.txt`). |
| README com instalação, configuração, execução e testes | Este documento, com comandos executados neste ambiente. |
| Stub não confundido com reconhecimento real | Versão `development-stub-v0`, `is_simulated=True`, aviso no log de inicialização e em cada inferência, e bloqueio em `APP_ENV=production`. |
| Inferência real executando | Verificado por HTTP com `VISION_PROVIDER=opencv`: modelo ONNX no `cv2.dnn`, foto real de banana → `banana` (0,3484) mapeada para o cadastro; maçã vermelha → `no_catalog_match` com `fruit: null`; latência medida. |
| Acurácia/adequação do modelo para o mercado | **Pendente e não afirmada**: exige dataset rotulado e treinamento; o modelo de referência não distingue variedades comerciais (ver "Próximos passos" e `models/README.md`). |
