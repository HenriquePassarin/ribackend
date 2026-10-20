# Modelos

Este diretório guarda os artefatos de modelo usados por `VISION_PROVIDER=opencv`.
Os arquivos binários **não** são versionados (ver `.gitignore`); use o script de
download, que confere o SHA-256 do artefato:

```bash
python scripts/fetch_model.py --list
python scripts/fetch_model.py --model mobilenetv2-7
```

O download é feito com `urllib` + verificação de hash por SSL; nenhuma credencial
é necessária.

## Modelo de referência incluído no registro

| Item | Valor |
| --- | --- |
| Nome | `mobilenetv2-7.onnx` |
| Origem | ONNX Model Zoo (`github.com/onnx/models`), MobileNetV2 |
| Treinado em | ImageNet-1k (1000 classes, ~1,2 M imagens) |
| SHA-256 | `c1c513582d56afceff8516c73804e484c81c6a830712ab6d682253f4a3cd042f` |
| Entrada | 224x224x3, RGB, `[0,1]`, normalizada com média `[0.485,0.456,0.406]` e desvio `[0.229,0.224,0.225]` |
| Saída | vetor de 1000 valores (**logits**; o grafo não inclui softmax) |
| Licença | conforme o ONNX Model Zoo (Apache-2.0 para este artefato) |

### Limites deste modelo (por que ele não resolve o problema do mercado)

- O ImageNet **não distingue variedades comerciais** (Gala, Fuji, Red Delicious),
  que é justamente o caso em que códigos e preços diferem.
- Várias frutas de hortifruti **não têm classe** no ImageNet: uva, manga, tomate,
  melão, pera, kiwi, mamão, entre outras.
- As classes de fruta existentes são de espécie ou de variedade única
  (`Granny Smith`, `orange`, `lemon`, `banana`, `pineapple`, `strawberry`,
  `pomegranate`, `fig`, `jackfruit`, `custard apple`).
- Verificação local com uma imagem por classe (sem métrica de acurácia): com a
  normalização ImageNet (RGB + mean/std) `banana`, `lemon`, `orange`, `strawberry`
  e `Granny Smith` foram classificadas corretamente com confiança alta; uma foto de
  maçã vermelha foi classificada como `pomegranate` (não existe classe de maçã
  vermelha). Sem essa normalização (BGR, sem mean/std) as mesmas fotos eram
  classificadas errado — por isso a configuração de pré-processamento importa.

Conclusão: use este modelo para validar a integração, medir latência e exercitar o
fluxo completo. Para identificar variedades comerciais, é necessário treinar um
classificador em um dataset de frutas rotulado para o seu contexto.

## Caminho recomendado para variedades comerciais

1. Reunir imagens autorizadas das frutas e variedades **reais do mercado**, com as
   condições de captura do uso (câmera, iluminação, embalagem, reflexos, etiquetas).
2. Como ponto de partida público existe o **Fruits-360** (Kaggle/Mendeley/GitHub,
   ~190 mil imagens e ~270 classes de frutas, legumes, castanhas e cogumelos). Ele
   contém variedades, mas é fotografado em fundo claro e com nomes que não
   correspondem necessariamente ao cadastro comercial — verifique licença e
   autorização de uso antes de treinar.
3. Treinar/ajustar o classificador, **separando treino/validação/teste sem
   vazamento de imagens quase idênticas**.
4. Exportar para ONNX e registrar aqui a URL e o SHA-256
   (`python scripts/fetch_model.py --name <nome> --url ... --sha256 ...`), ou
   copiar o arquivo e apontar `MODEL_PATH` para ele.
5. Medir precisão/recall/F1 por classe, matriz de confusão, taxa de não
   reconhecimento e latência, e só então calibrar `MIN_RECOGNITION_CONFIDENCE`.

Nenhum dataset, treinamento ou métrica é distribuído neste repositório.
