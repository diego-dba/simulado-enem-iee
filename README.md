# 🎓 Sistema Híbrido OMR + IA para Correção de Simulado (ENEM)

Este projeto automatiza a correção de cartões-resposta de um simulado escolar (modelo ENEM). A arquitetura combina visão computacional clássica (OpenCV) para leitura rápida de milhares de bolhas com Inteligência Artificial Generativa (Google Gemini) para transcrição de manuscritos (cabeçalhos, nomes e turmas).

*Nota: Parte da arquitetura, lógica e refatoração de código deste projeto foi desenvolvida em colaboração ativa com as IAs Gemini e Claude, atuando como "copilotos" e mentores.*

## 🚀 Arquitetura e Fluxo de Dados
1. **Fase 1 (Processamento Híbrido):** 
   - Script Python (`corretor_gabaritos_bolhas.py`) lê PDFs digitalizados.
   - **OpenCV** extrai a matriz de bolhas marcadas e processa as respostas.
   - **Gemini API** transcreve o texto manuscrito de cabeçalho em formato estruturado (JSON).
   - O script gera arquivos CSV exportáveis por dia de prova.
2. **Fase 2 (Banco de Dados e Regras de Negócio):** 
   - Importação dos dados no Google Sheets.
   - Relacionamento de chaves primárias (Matrícula e Turma).
   - Aplicação de regras de eliminação (rasura, marcações duplas/X).
   - Cálculo de notas, absenteísmo e geração de Rankings Gerais.
3. **Fase 3 (Automação de E-mails):**
   - Disparo em massa do boletim individual (notas, ranking e links importantes) aos alunos usando Google Apps Script (GAS).

## 🛠️ Tecnologias
- `Python` + `OpenCV` + `PyMuPDF` + `Pandas`
- `Google Gemini API` (Transcrições estruturadas e cache para otimização de chamadas)
- `Google Sheets` & `Google Apps Script`

## ⚙️ Uso (Desenvolvimento)
### Pré-requisitos
1. Clone o repositório.
2. Instale as dependências: `pip install -r requirements.txt`
3. Crie um arquivo `.env` na raiz do projeto com a variável: `GEMINI_API_KEY=sua-chave-aqui`

### Execução
```bash
# Para o Dia 1 (60 questões + Leitura de Idioma)
python corretor_gabaritos_bolhas.py --dia 1 "pdfs_digitalizados/*.pdf"

# Para rodar sem chamar a IA (Apenas OMR OpenCV, sem custos de API)
python corretor_gabaritos_bolhas.py --dia 2 "pdfs_digitalizados/*.pdf" --sem-ia