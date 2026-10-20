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
121 passed, 1 warning in 7.28s
```

Os 121 testes cobrem saúde, consulta/cadastro de frutas, upload e validação de imagens,
política de confiança, estados de reconhecimento, confirmação/correção, configuração, o
adaptador simulado e o adaptador OpenCV (decodificação, pré-processamento incluindo
escala/média/desvio, logits/softmax, mapeamento de rótulos e falhas do modelo). Nenhum teste unitário depende
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
2. `cv2.dnn.blobFromImage` faz redimensionamento, escala e troca de canais; em
   seguida o blob é normalizado por canal com `(blob - média) / desvio`. Ambos são
   configuráveis — o MobileNetV2 do registro **exige** RGB com mean/std do ImageNet
   (sem isso, as previsões saem erradas).
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
MODEL_INPUT_MEAN=0.485,0.456,0.406
MODEL_INPUT_STD=0.229,0.224,0.225
MODEL_SWAP_RB=true
MODEL_OUTPUT_SOFTMAX=auto
```

> Se o seu `.env` ainda tem a configuração antiga (`MODEL_INPUT_MEAN=0,0,0`,
> `MODEL_SWAP_RB=false` e nenhum `MODEL_INPUT_STD`), atualize para o trecho acima.
> Sem RGB + mean/std o MobileNetV2 classifica errado (por exemplo, banana como
> `stingray`).

O vínculo com o cadastro continua por `fruit.vision_label`, que deve conter exatamente o
rótulo da classe do modelo (por exemplo `banana`). Sem correspondência, o status é
`no_catalog_match` e nenhum dado comercial é inventado.

### Verificação executada (resultados reais)

Servidor local com `VISION_PROVIDER=opencv` e o modelo MobileNetV2 do registro, sobre
fotos reais de frutas (imagens usadas só para verificação local e não versionadas):

| Caso | Resposta observada |
| --- | --- |
| Foto real de banana (fruta cadastrada com `vision_label=banana`) | `label=banana`, `confidence=1.0`, `fruit.code=00002` com preço vindo do cadastro |
| Foto real de limão (fruta cadastrada com `vision_label=lemon`) | `label=lemon`, `confidence=0.9798` |
| Foto real de laranja (fruta cadastrada com `vision_label=orange`) | `label=orange`, `confidence=0.9310` |
| Foto real de morango (fruta cadastrada com `vision_label=strawberry`) | `label=strawberry`, `confidence=0.7825` (abaixo do limiar de exemplo: `confirmation_required`) |
| Foto real de maçã vermelha (sem classe correspondente) | `no_catalog_match`, `label=pomegranate`, `confidence=0.9537`, `fruit=null` |
| `README.md` enviado como `image/png` | `400 INVALID_IMAGE` |

Esses números foram medidos com a normalização ImageNet habilitada
(`MODEL_SWAP_RB=true`, `MODEL_INPUT_MEAN=0.485,0.456,0.406`,
`MODEL_INPUT_STD=0.229,0.224,0.225`). Com o pré-processamento anterior (BGR, sem
mean/std), as mesmas fotos saíam erradas: banana → `stingray`, limão → `picket
fence`, laranja → `lampshade`, Granny Smith → `plate rack`. As imagens foram usadas
apenas para verificação local e não estão versionadas.

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
- a confiança varia bastante (de ~0,78 a 1,0 nas verificações acima): é um softmax sobre
  1000 classes de objetos, não de frutas — o que reforça a necessidade de
  `ALWAYS_REQUIRE_CONFIRMATION` e de calibrar `MIN_RECOGNITION_CONFIDENCE` com experimentos.

Para identificar variedades é necessário treinar um classificador em um dataset rotulado
(começando pelas frutas reais do mercado; `models/README.md` descreve o caminho,
incluindo o uso do Fruits-360 como ponto de partida público e a verificação de licença e
autorização). Exportar para ONNX e registrar URL + SHA-256 é suficiente para o adaptador
funcionar: nenhum código precisa mudar para trocar de modelo.

**As verificações acima são apenas checagens de integração** (poucas imagens), não
avaliação de qualidade do MobileNetV2/ImageNet. Um dataset público foi preparado e uma
**baseline de classificação** foi treinada nele; as métricas dessa baseline estão na
seção seguinte e valem para os recortes do dataset, não para o balcão real.

## Dataset de frutas (Roboflow)

Dataset escolhido: **Fruits by YOLO** (`fruitsdetection/fruits-by-yolo`, versão 1),
licença **CC BY 4.0** (crédito ao autor no Roboflow Universe). São 2.974 imagens em
640×640 (2.697 treino / 187 validação / 90 teste), com augmentação de flip
horizontal/vertical, rotação, shear e blur.

Classes (9): `Apple`, `Banana`, `Grapes`, `Kiwi`, `Mango`, `Orange`, `Pineapple`,
`Sugerapple` (grafia do dataset para *sugar apple*), `Watermelon`.

O que a inspeção do arquivo baixado revelou:

- as anotações são **polígonos** (segmentação), embora a página do Universe anuncie
  “Object Detection”; 7 linhas vieram no formato de caixa e foram convertidas para
  retângulos, porque rótulos de segmentação não aceitam caixas misturadas;
- 8 imagens não têm nenhuma anotação (fundo) e são mantidas como negativas;
- o `data.yaml` original referencia `../train/images`, que não resolve com o YAML na
  raiz; o script normaliza para `train/images`, `valid/images` e `test/images`.

Preparar o dataset (não treina):

```bash
cd backend
python scripts/prepare_dataset.py --zip "<caminho>/Fruits by YOLO.v1-fruits-detection.yolo26.zip"
```

O resultado fica em `datasets/fruits-by-yolo-v1/` (ignorado pelo git): `data.yaml`
normalizado, `classes.txt` e `dataset_report.json` com contagens por split e por classe.

Números da última execução: **2.974 imagens, 6.362 polígonos**, sem problemas de
integridade (imagem sem rótulo, rótulo órfão, classe inválida ou coordenada fora de
`[0,1]`). Distribuição por classe:

| Classe | Instâncias |
| --- | ---: |
| Orange | 990 |
| Watermelon | 890 |
| Sugerapple | 828 |
| Kiwi | 815 |
| Mango | 762 |
| Banana | 637 |
| Apple | 547 |
| Grapes | 527 |
| Pineapple | 366 |

Treinar depois (opcional; exige `ultralytics`, que não é dependência padrão):

```bash
python -m pip install ultralytics
python scripts/train_yolo.py --epochs 50 --export-onnx
```

O script treina segmentação (`yolo11n-seg.pt`) e, com `--export-onnx`, exporta o melhor
peso. Esse treino de detecção **não foi executado** (em CPU seriam horas por dezenas de
épocas). Além disso, um ONNX de segmentação/detecção **não** é compatível com o
adaptador atual, que espera um classificador de classe única — usá-lo na API exige um
adaptador de detecção (pegar a detecção de maior confiança e mapear a classe para
`vision_label`).

### Baseline treinada (classificador)

Para medir o quanto o dataset ajuda de fato, foi treinada uma baseline de
**classificação** sobre recortes das anotações (uma fruta por recorte), que já é
compatível com o adaptador atual:

1. `scripts/prepare_classifier_crops.py` gera 6.362 recortes (margem de 12%) em
   `datasets/fruits-by-yolo-v1-crops/` — 5.753 treino / 394 validação / 215 teste.
2. `scripts/train_classifier.py --freeze-backbone` ajusta só a cabeça de um
   MobileNetV2 pré-treinado no ImageNet, por 6 épocas em CPU (~5 min/época).
3. `scripts/export_classifier_onnx.py` exporta
   `models/fruits-mobilenetv2-baseline.onnx` (8,9 MB, SHA-256
   `bad1e539e91c98b40835edcaf103a5acd1e8f1d3c0d814f4aa2af316f6ce2886`).

Resultado no split de **teste** (215 recortes, nunca usados em treino/validação):

| Métrica | Valor |
| --- | ---: |
| Acurácia | **96,74%** |
| F1 macro (8 classes com suporte) | **0,9514** |
| F1 ponderado | 0,9711 |

| Classe | Precisão | Recall | F1 | Suporte |
| --- | ---: | ---: | ---: | ---: |
| Apple | 1,000 | 0,909 | 0,952 | 11 |
| Banana | 1,000 | 0,980 | 0,990 | 50 |
| Grapes | 1,000 | 1,000 | 1,000 | 17 |
| Kiwi | 1,000 | 1,000 | 1,000 | 28 |
| Mango | 0,588 | 1,000 | 0,741 | 10 |
| Orange | 1,000 | 0,924 | 0,961 | 53 |
| Pineapple | 1,000 | 1,000 | 1,000 | 30 |
| Sugerapple | — | — | — | 0 |
| Watermelon | 1,000 | 0,938 | 0,968 | 16 |

O único defeito visível é o excesso de Mango: 7 recortes de outras frutas foram
classificados como Mango (daí precisão 0,588). `Sugerapple` não tem nenhum recorte no
teste, então não entra no macro.

Verificação de integração: o ONNX carregado pelo `cv2.dnn` reproduziu a mesma acurácia
do PyTorch (96,74%), com 21,5 ms por inferência (CPU) e concordância de 98,1% entre os
dois. Na API real, um recorte de banana retornou `label=Banana`, confiança 0,9979,
`status=recognized` e a fruta cadastrada; um recorte de melancia (sem cadastro) retornou
`no_catalog_match`.

Pré-requisitos para reproduzir: `pip install torch torchvision onnx` (não são
dependências da API) e os passos acima. Para usar a baseline, aponte o `.env`:

```ini
MODEL_PATH=models/fruits-mobilenetv2-baseline.onnx
MODEL_LABELS_PATH=models/fruits-mobilenetv2-baseline.labels.txt
MODEL_INPUT_SIZE=224
MODEL_INPUT_SCALE=0.00392156862745098
MODEL_INPUT_MEAN=0.485,0.456,0.406
MODEL_INPUT_STD=0.229,0.224,0.225
MODEL_SWAP_RB=true
MODEL_OUTPUT_SOFTMAX=true
```

Depois reinicie o `uvicorn` e cadastre as frutas com `vision_label` igual ao rótulo do
modelo (`Banana`, `Orange`, ...), não aos nomes do ImageNet.

**Limites desta baseline:** treinada com backbone congelado sobre recortes com 12% de
margem em torno da anotação (não na foto inteira do caixa); os 96,74% valem para esse
split, não para o balcão real; não distingue variedades comerciais; e o teste não tem
`Sugerapple`.

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
| `MODEL_INPUT_MEAN` | `0,0,0` | Média por canal **aplicada depois da escala**: `(valor - média) / desvio`. Use a ordem de canais resultante de `MODEL_SWAP_RB`. |
| `MODEL_INPUT_STD` | `1,1,1` | Desvio padrão por canal, aplicado depois da média. Para ImageNet: `0.229,0.224,0.225`. |
| `MODEL_SWAP_RB` | `false` | Troca de canais B/R quando o modelo espera RGB (obrigatório para o MobileNetV2 do registro). |
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
  testes. O pré-processamento escala o blob e depois aplica `(valor - média) / desvio` por
  canal, na ordem de canais resultante de `MODEL_SWAP_RB`; a configuração do MobileNetV2 do
  registro exige RGB e mean/std do ImageNet. O modelo carregado é cacheado por
  configuração e serializado por `Lock`. `MODEL_OUTPUT_SOFTMAX=auto` trata modelos que
  devolvem logits (caso dos artefatos da ONNX Model Zoo) sem exigir que o operador saiba
  disso.
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

- **Baseline avaliada apenas em recortes do dataset.** A acurácia de 96,74% e o F1
  macro de 0,9514 valem para o split de teste do Fruits by YOLO v1 (recortes com 12% de
  margem), não para fotos do balcão real nem para variedades comerciais. O treino do
  detector YOLO não foi executado.
- **Treino fora do fluxo da aplicação.** `scripts/fetch_model.py` só baixa artefatos
  publicados; `prepare_dataset.py`, `prepare_classifier_crops.py`,
  `train_classifier.py`, `export_classifier_onnx.py` e `train_yolo.py` são ferramentas
  manuais e exigem `torch`/`onnx` ou `ultralytics` instalados à parte — nada disso é
  usado pela API em execução.
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
├── datasets/                        # dataset YOLO preparado (ignorado pelo git)
├── scripts/
│   ├── fetch_model.py               # baixa/verifica modelo ONNX (SHA-256)
│   ├── prepare_dataset.py           # extrai/valida dataset YOLO do Roboflow
│   ├── train_yolo.py                # treina/exporta ONNX (requer ultralytics)
│   └── seed_dev_data.py             # dados de exemplo FICTÍCIOS
├── tests/                           # 121 testes (pytest)
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
| Testes automatizados críticos passam | `121 passed` (Python 3.12.3, `requirements-dev.txt`). |
| README com instalação, configuração, execução e testes | Este documento, com comandos executados neste ambiente. |
| Stub não confundido com reconhecimento real | Versão `development-stub-v0`, `is_simulated=True`, aviso no log de inicialização e em cada inferência, e bloqueio em `APP_ENV=production`. |
| Inferência real executando | Verificado por HTTP com `VISION_PROVIDER=opencv` e normalização ImageNet: modelo ONNX no `cv2.dnn`, foto real de banana → `banana` (1,0) mapeada para o cadastro; limão → `lemon` (0,9798); laranja → `orange` (0,9310); maçã vermelha → `no_catalog_match` com `fruit: null`; latência medida. |
| Acurácia/adequação do modelo para o mercado | **Pendente e não afirmada**: exige dataset rotulado e treinamento; o modelo de referência não distingue variedades comerciais (ver "Próximos passos" e `models/README.md`). |
