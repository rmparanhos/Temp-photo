# Photo Dedup

TUI para encontrar fotos similares, pontuar a qualidade de cada uma e mover as duplicatas para uma pasta separada.

---

## Como usar

```bash
pip install -r requirements.txt
python main.py ./suas-fotos
```

Flags opcionais:

| Flag | Padrão | Descrição |
|---|---|---|
| `--threshold N` | 10 | Sensibilidade de similaridade (0 = idênticas, 64 = qualquer coisa) |
| `--recursive` / `-r` | off | Escanear subpastas |

### Navegação na TUI

| Tecla | Ação |
|---|---|
| `↑` / `↓` | Mudar qual foto será mantida no grupo |
| `Enter` | Confirmar decisão e ir para o próximo grupo |
| `S` | Pular grupo (não toca em nenhuma foto) |
| `Q` | Sair |

Ao final, uma tela de confirmação lista tudo que será movido. As duplicatas vão para `_duplicates/` dentro da pasta escaneada.

---

## Estrutura do projeto

```
photo_dedup/
├── scanner.py   — carrega fotos, calcula pHash, agrupa similares
├── scorer.py    — heurísticas de qualidade (pontua cada foto de 0 a 100)
└── tui.py       — interface TUI com Textual
main.py          — entry point (argumentos de linha de comando)
requirements.txt
```

---

## Conceitos

### pHash — Perceptual Hash

Um hash convencional (MD5, SHA) muda completamente se um único pixel for diferente. O **pHash** foi criado para o problema oposto: gerar um "resumo" da imagem que seja *parecido* para imagens visualmente parecidas.

**Como funciona:**

1. Reduz a imagem para ~32×32 pixels (elimina detalhes, preserva estrutura)
2. Converte para escala de cinza
3. Aplica a **DCT** (Discrete Cosine Transform) — a mesma transformada usada internamente pelo JPEG — que separa as frequências da imagem do mais grosso ao mais fino
4. Pega só as frequências baixas (o "esqueleto visual"), descartando texturas e ruído
5. Compara cada coeficiente com a média: se maior → `1`, se menor → `0`
6. Resultado: uma string de 64 bits, a "impressão digital" da foto

**Distância de Hamming:** para comparar dois hashes, conta-se quantos bits diferem. Isso é a distância de Hamming.

- Distância `0` → fotos idênticas
- Distância `≤ 10` → mesma cena, pequenas variações (brilho, compressão, leve crop)
- Distância `> 20` → cenas diferentes

O `--threshold` controla esse limite.

---

### Variância do Laplaciano — nitidez

O **operador Laplaciano** calcula a segunda derivada da imagem — ou seja, onde a intensidade dos pixels muda *abruptamente*. Bordas nítidas produzem respostas altas; bordas borradas produzem respostas baixas.

O kernel usado:

```
 0   1   0
 1  -4   1
 0   1   0
```

Aplicamos esse kernel a cada pixel (convolução) e calculamos a **variância** do resultado:

- **Variância alta** → muitas bordas bem definidas → foto **nítida**
- **Variância baixa** → tudo suave → foto **borrada**

É a heurística de nitidez mais usada justamente por ser rápida e funcionar bem com Pillow + NumPy, sem precisar de OpenCV.

---

### Score de exposição

Analisa o histograma de brilho da imagem:

- **Brilho médio perto de 128** (meio-tom) → bem exposta
- **Desvio padrão alto** → bom contraste
- Fotos muito escuras (subexpostas) ou muito claras (superexpostas) são penalizadas

---

### Score de ruído

Compara a imagem original com uma versão borrada por filtro mediano. O filtro mediano preserva bordas mas elimina ruído granular (salt-and-pepper). O **resíduo** entre as duas é uma estimativa do nível de ruído:

- Resíduo baixo → imagem limpa → pontuação alta
- Resíduo alto → muito ruído → pontuação baixa

---

### Score EXIF

Se os metadados EXIF estiverem disponíveis:

- **ISO baixo** (ex: 100) → sensor menos sensível → menos ruído → melhor pontuação
- **Velocidade de obturador rápida** (ex: 1/500s) → menos motion blur → melhor pontuação

Quando o EXIF não está disponível, o score é 50 (neutro).

---

### Score final

Média ponderada dos cinco critérios:

| Critério | Peso |
|---|---|
| Nitidez (Laplaciano) | 35% |
| Exposição | 25% |
| Resolução (MP) | 20% |
| Ruído | 15% |
| EXIF | 5% |

A foto com maior score é sugerida como a que deve ser mantida. O usuário pode substituir a escolha na TUI antes de confirmar.

---

## Próximos passos (v2)

- **Super foto por média ponderada:** tira a média dos pixels de N fotos similares, ponderada pelo score de nitidez de cada uma. O ruído, sendo aleatório, se cancela — o resultado é uma imagem mais limpa do que qualquer uma individualmente.
