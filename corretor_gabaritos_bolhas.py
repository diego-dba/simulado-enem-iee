"""
Leitor de Gabaritos do Simulado ENEM 2026 3ª série

Juntei meu código Leitor Python com a IA Gemini para corrigir os cartões-resposta do 1º e do 2º dia.
O OpenCV lê as bolhas e a IA Gemini lê só o texto manuscrito do cabeçalho.

Uso:
    py corrigir_final.py --dia 1 Turma_001.pdf
    py corrigir_final.py --dia 2 "pasta/*.pdf"
    py corrigir_final.py --dia 2 Turma_001.pdf --sem-ia     # só bolhas e sem custo

Versão atual: 1.5

Histórico de versões

Versão 1.0
    Uni a leitura das bolhas com OpenCV e a leitura do cabeçalho com a IA Gemini
    Cartão do 1º dia com 60 questões

Versão 1.1
    Passei a mandar para a IA só o recorte do cabeçalho
    Guardo as leituras da IA em cache
    Mostro os tokens gastos no terminal

Versão 1.2
    Passei a salvar uma imagem de evidência por cartão para os recursos dos alunos

Versão 1.3
    Marca duvidosa passou a contar como erro e a ser exportada como X
    Corrigi o idioma em branco que zerava a prova inteira

Versão 1.4
    Incluí o cartão do 2º dia com 70 questões e o parâmetro --dia
    Incluí os acertos por área e a coluna revisar_valeria_ponto

Versão 1.5
    Data: 05/10/2026
    Dupla marcação passou a ser exportada como Y e a entrar na coluna revisar
    Dupla marcação passou a ter prioridade sobre marca duvidosa
    Escrevi o cabeçalho e as regras de negócio

Espaço para novas alterações

Versão 1.6
    Data:
    Alteração:

Regras de negócio

Juntei meu código Leitor Python com a IA Gemini. As regras são:

1. Escolho o dia da prova com o parâmetro --dia. O dia 1 tem 60 questões e o dia 2 tem 70 questões.
   O dia define o gabarito oficial e o desenho da grade de bolhas.

2. Peço para a IA Gemini somente o texto manuscrito do cabeçalho. Isso é a turma e o nome e a frase da capa.
   A turma vem só do campo TURMA do cartão.
   Se o nome estiver em branco ele fica em branco. Nunca deduzo o nome pela assinatura nem pela frase.
   A frase ilegível vira ilegível e a frase vazia vira em branco.

3. Mando para a IA só o recorte do cabeçalho com resolução baixa para gastar menos tokens.
   Cada leitura fica em cache e nunca pago duas vezes pelo mesmo cartão.

4. No dia 1 leio a opção de língua estrangeira com o OpenCV e não com a IA.
   Inglês usa o gabarito de inglês nas questões 01 a 03. Espanhol usa o gabarito de espanhol.
   Idioma em branco ou marcado duas vezes faz as questões 01 a 03 não pontuarem e as demais continuam valendo.
   No dia 2 não existe escolha de idioma.

5. Acho as bolhas com o OpenCV e monto a grade das questões.
   Se o número de bolhas ou de colunas não bater com o desenho do cartão marco ERRO GRADE e não corrijo aquele cartão.

6. Classifico cada questão nesta ordem de prioridade:
    6.1 Mais de uma marca forte vira Y. O aluno duplicou a resposta.
    6.2 Marca fraca ou duvidosa vira X. Uma marca forte junto com uma marca fraca também vira X.
    6.3 Uma única marca forte vira a letra marcada.
    6.4 Nenhuma marca vira traço. É a questão em branco.
   Considero marca forte a que passa do limite T_MARCA e duvidosa a que fica entre T_DUVIDA e T_MARCA.

7. Corrijo comparando só a letra marcada com o gabarito oficial.
   Y e X e traço nunca pontuam. O total soma as questões 01 a 60 no dia 1 e 01 a 70 no dia 2.
   Também separo os acertos por área.

8. As questões Y e X entram na coluna revisar.
   A coluna revisar_valeria_ponto lista as questões X em que a bolha mais escura é a resposta certa.
   Essas são as que confiro primeiro na evidência.

9. Salvo para cada cartão a folha inteira com círculo verde no acerto e vermelho no erro e laranja no X e no Y.
   O id_leitura liga a linha da planilha ao arquivo da evidência.

10. Exporto um CSV por dia pronto para importar no Google Planilhas.
    Na coluna respostas a letra é a marcação única e X é marca duvidosa e Y é dupla marcação e traço é em branco.
"""
import sys, os, json, time, glob, argparse
import numpy as np
import cv2
import pandas as pd
import pymupdf as fitz

# ---------- CONFIG 
MODELO = "gemini-3.8-flash"   
MEDIA_RES = "LOW"             
DPI_IA = 110
DEBUG = True                  

# ---------- GABARITOS OFICIAIS 
ING, ESP = "DBE", "DED"                                 # questões 01-03 (idioma)
LING = "DBBEECDBBABBCDCBEEEACBECDCA"                    # 1º dia, questões 04-30
CH   = "DBCBDEBBBDEBBADDBAEEBEEBCCDDED"                 # 1º dia, questões 31-60
MAT  = "EDEADCADCCDEBADACAABACECBBBABADAEBC"            # 2º dia, questões 01-35
CN   = "EEBBBBCDDBDDCDCCCDBBDBCEEDBDCCEEEDC"            # 2º dia, questões 36-70

DIAS = {
    1: dict(colunas=[20, 20, 20], crop=(0.095, 0.495), tem_lingua=True,
            gab={"INGLES": ING + LING + CH, "ESPANHOL": ESP + LING + CH},
            areas=[("linguagens", 1, 30), ("ciencias_humanas", 31, 60)]),
    2: dict(colunas=[20, 20, 20, 10], crop=(0.105, 0.495), tem_lingua=False,
            gab={"UNICO": MAT + CN},
            areas=[("matematica", 1, 35), ("ciencias_natureza", 36, 70)]),
}
for d, c in DIAS.items():
    for k, v in c["gab"].items():
        assert len(v) == sum(c["colunas"]), (d, k, len(v))

DPI = 150
T_MARCA, T_DUVIDA = 60, 35
RAIO_MIN, RAIO_MAX = 8, 15

PROMPT = """Cartão-resposta preenchido à mão. Transcreva EXATAMENTE como escrito, sem corrigir nem completar:
- turma: número do campo "TURMA:" (ex.: "001")
- nome: texto das caixinhas de "NOME COMPLETO:" (se ocupar 2 linhas, junte). Vazio = ""
- frase_capa: texto da caixa "ESCREVA AQUI A FRASE QUE CONSTA NA CAPA...". Vazia = "em branco"; ininteligível = "ilegível"
IGNORE a assinatura e NÃO deduza o nome por ela nem pela frase.
Responda só JSON: {"turma":"","nome":"","frase_capa":""}"""

TOTAL = {"chamadas": 0, "entrada": 0, "saida": 0, "pensamento": 0, "total": 0}
client = None


# ---------- IA 
def criar_cliente():
    from dotenv import load_dotenv
    from google import genai
    load_dotenv()
    chave = os.getenv("GEMINI_API_KEY")
    if not chave:
        sys.exit("❌ A chave da API não foi encontrada no arquivo .env!")
    return genai.Client(api_key=chave)


def chamar_ia(jpg, com_thinking):
    from google.genai import types
    cfg = dict(response_mime_type="application/json", temperature=0.0,
               media_resolution=getattr(types.MediaResolution, f"MEDIA_RESOLUTION_{MEDIA_RES}"))
    if com_thinking:
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
    return client.models.generate_content(
        model=MODELO,
        contents=[types.Part.from_bytes(data=jpg, mime_type="image/jpeg"), PROMPT],
        config=types.GenerateContentConfig(**cfg))


def extrair_cabecalho_ia(page, pag, tag, crop):
    r = page.rect
    clip = fitz.Rect(0, r.height * crop[0], r.width, r.height * crop[1])
    pix = page.get_pixmap(dpi=DPI_IA, clip=clip)
    jpg = pix.tobytes("jpeg", jpg_quality=85)
    if DEBUG:
        with open(f"debug_ia_{tag}.jpg", "wb") as f:       
            f.write(jpg)
    try:
        try:
            resp = chamar_ia(jpg, True)
        except Exception as e:
            if "thinking" in str(e).lower():
                resp = chamar_ia(jpg, False)                
            else:
                raise
        u = resp.usage_metadata
        ent = getattr(u, "prompt_token_count", 0) or 0
        sai = getattr(u, "candidates_token_count", 0) or 0
        pen = getattr(u, "thoughts_token_count", 0) or 0
        tot = getattr(u, "total_token_count", 0) or 0
        TOTAL["chamadas"] += 1
        TOTAL["entrada"] += ent; TOTAL["saida"] += sai
        TOTAL["pensamento"] += pen; TOTAL["total"] += tot
        print(f"      [tokens] entrada {ent} | saída {sai} | pensamento {pen} | total {tot}")
        d = json.loads(resp.text)
        return {k: str(d.get(k, "")) for k in ("turma", "nome", "frase_capa")}
    except Exception as e:
        print(f"      [Aviso] Erro na IA: {e}")
        return None


# ---------- BOLHAS 
def escuridao(gray, x, y, r):
    m = np.zeros(gray.shape, np.uint8)
    cv2.circle(m, (int(x), int(y)), int(r * 0.6), 255, -1)
    return 255 - cv2.mean(gray, mask=m)[0]


def agrupar(vals, tol, n):
    vals = np.sort(np.array(vals))
    grupos = np.split(vals, np.where(np.diff(vals) > tol)[0] + 1)
    grupos = sorted(grupos, key=len, reverse=True)[:n]
    return sorted(float(np.median(g)) for g in grupos)


def montar_grade(gray, tag, colunas):
    """Devolve uma lista com uma linha por questão, 5 bolhas nesse caso,, na ordem das questões."""
    h, w = gray.shape
    top = int(h * 0.50)
    _, binaria = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(binaria[top:], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pts, raios = [], []
    lim_min, lim_max = 2 * RAIO_MIN, 2 * RAIO_MAX + 6
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if lim_min <= cw <= lim_max and lim_min <= ch <= lim_max and 0.8 <= cw / ch <= 1.25:
            pts.append((x + cw / 2, y + ch / 2 + top)); raios.append((cw + ch) / 4)
    if not pts:
        return None
    pts, raios = np.array(pts), np.array(raios)
    dentro = pts[:, 1] < 0.92 * h                        
    pts, raios = pts[dentro], raios[dentro]
    esperado = 5 * sum(colunas)
    print(f"  {tag}: {len(pts)} bolhas (esperado {esperado})")
    if len(pts) < 0.66 * esperado:
        return None
    r = float(np.median(raios))

    ncol = len(colunas)
    xs = np.sort(pts[:, 0])
    idx = np.sort(np.argsort(np.diff(xs))[-(ncol - 1):])  
    cortes = [(xs[i] + xs[i + 1]) / 2 for i in idx]
    bordas = [-np.inf] + cortes + [np.inf]
    cols = [pts[(pts[:, 0] >= a) & (pts[:, 0] < b)] for a, b in zip(bordas[:-1], bordas[1:])]

    grade = []
    for k, (col, nlin) in enumerate(zip(cols, colunas), 1):
        if len(col) == 0:
            return None
        xc, yc = agrupar(col[:, 0], 14, 5), agrupar(col[:, 1], 15, nlin)
        if len(xc) != 5 or len(yc) != nlin:
            print(f"  coluna {k}: {len(xc)} letras e {len(yc)} linhas (esperado 5 e {nlin})")
            return None
        for yy in yc:
            grade.append(np.array([[xx, yy, r] for xx in xc]))
    if DEBUG:
        img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        for lin in grade:
            for x, y, r_ in lin:
                cv2.circle(img, (int(x), int(y)), int(r_), (0, 0, 255), 1)
        cv2.imwrite(f"debug_{tag}.png", img)
    return grade


def ler_lingua(gray):
    h, w = gray.shape
    r = 0.012 * w
    ing = escuridao(gray, 0.367 * w, 0.1246 * h, r)
    esp = escuridao(gray, 0.515 * w, 0.1246 * h, r)
    if max(ing, esp) < T_MARCA: return "EM BRANCO"
    if min(ing, esp) >= T_MARCA: return "DUPLA"
    return "INGLES" if ing > esp else "ESPANHOL"


# ---------- EVIDÊNCIA 
def salvar_evidencia(rgb, grade, resp, gab, pontua, tag, acertos, rodape, pasta):
    img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    for q, (lin, rq) in enumerate(zip(grade, resp), 1):
        if rq in "ABCDE":
            x, y, r = lin["ABCDE".index(rq)]
            cor = (0, 160, 0) if (pontua(q) and rq == gab[q - 1]) else (0, 0, 255)   
            cv2.circle(img, (int(x), int(y)), int(r) + 3, cor, 2)
        elif rq in ("X", "Y"):                                                         
            for x, y, r in lin:
                cv2.circle(img, (int(x), int(y)), int(r) + 3, (0, 165, 255), 2)
    cv2.putText(img, f"{tag} | {rodape}acertos: {acertos}", (20, img.shape[0] - 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    cv2.putText(img, "verde = acerto | vermelho = erro | laranja = X duvidosa ou Y dupla marcacao (conta como erro)",
                (20, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1)
    cv2.imwrite(f"{pasta}/{tag}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])


# ---------- PIPELINE ----------
def processar(pdf, dia, cfg, cache, cache_path, usar_ia, pasta_ev):
    arq = os.path.basename(pdf)
    base = os.path.splitext(arq)[0]
    linhas = []
    for pag, page in enumerate(fitz.open(pdf), 1):
        tag = f"dia{dia}_{base}_p{pag:03d}"
        print(f"Processando {arq} (dia {dia}) - Página {pag}...")
        pix = page.get_pixmap(dpi=DPI)
        rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        chave = f"{arq}|{pag}"
        if not usar_ia:
            t = {"turma": "", "nome": "", "frase_capa": ""}
        elif chave in cache:
            t = cache[chave]; print("      [cache] texto já lido, sem custo")
        else:
            t = extrair_cabecalho_ia(page, pag, tag, cfg["crop"])
            if t:
                cache[chave] = t
                json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
            else:
                t = {"turma": "ERRO IA", "nome": "ERRO IA", "frase_capa": ""}
            time.sleep(0.5)

        if cfg["tem_lingua"]:
            lingua = ler_lingua(gray)
            lingua_ok = lingua in ("INGLES", "ESPANHOL")
            gab = cfg["gab"][lingua] if lingua_ok else cfg["gab"]["INGLES"]   # sem idioma: só 01-03 não pontuam
            pontua = lambda q, ok=lingua_ok: q > 3 or ok
            rodape = f"idioma: {lingua} | "
        else:
            lingua = None
            gab = cfg["gab"]["UNICO"]
            pontua = lambda q: True
            rodape = ""

        reg = {"id_leitura": tag, "arquivo": arq, "pagina": pag,
               "turma": t["turma"], "nome": t["nome"], "frase_capa": t["frase_capa"]}
        if lingua is not None:
            reg["lingua"] = lingua

        grade = montar_grade(gray, tag, cfg["colunas"])
        if grade is None:
            reg.update(acertos="", revisar="ERRO GRADE", respostas="")
            linhas.append(reg); continue

        baseline = np.median([escuridao(gray, x, y, r) for lin in grade for x, y, r in lin])
        resp, hits, revisar, valeria = [], [], [], []
        for q, lin in enumerate(grade, 1):
            f = [escuridao(gray, x, y, r) - baseline for x, y, r in lin]
            marcadas = [i for i, v in enumerate(f) if v > T_MARCA]
            duvidas = [i for i, v in enumerate(f) if T_DUVIDA < v <= T_MARCA]
            acertou = False
            if len(marcadas) > 1:
                resp.append("Y"); revisar.append(q)
            elif duvidas:
                resp.append("X"); revisar.append(q)
                if pontua(q) and "ABCDE"[int(np.argmax(f))] == gab[q - 1]:
                    valeria.append(q)
            elif len(marcadas) == 1:
                letra = "ABCDE"[marcadas[0]]
                resp.append(letra)
                acertou = pontua(q) and letra == gab[q - 1]
            else:
                resp.append("-")
            hits.append(acertou)

        acertos = int(sum(hits))
        salvar_evidencia(rgb, grade, resp, gab, pontua, tag, acertos, rodape, pasta_ev)
        reg["acertos"] = acertos
        for nome_area, ini, fim in cfg["areas"]:
            reg[f"acertos_{nome_area}"] = int(sum(hits[ini - 1:fim]))
        reg["revisar"] = ",".join(map(str, revisar))
        reg["revisar_valeria_ponto"] = ",".join(map(str, valeria))
        reg["respostas"] = "".join(resp)
        for q, x in enumerate(resp, 1):
            reg[f"q{q:02d}"] = x
        linhas.append(reg)
    return linhas


def main():
    global client
    ap = argparse.ArgumentParser()
    ap.add_argument("--dia", type=int, choices=[1, 2], required=True)
    ap.add_argument("--sem-ia", action="store_true", help="só lê as bolhas (nome, turma e frase ficam vazios)")
    ap.add_argument("pdfs", nargs="+")
    a = ap.parse_args()

    cfg = DIAS[a.dia]
    usar_ia = not a.sem_ia
    if usar_ia:
        client = criar_cliente()
    cache_path = f"cache_textos_dia{a.dia}.json"
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    pasta_ev = f"evidencias_dia{a.dia}"
    os.makedirs(pasta_ev, exist_ok=True)

    pdfs = [p for arg in a.pdfs for p in (sorted(glob.glob(arg)) or [arg])]
    dados = []
    for pdf in pdfs:
        dados.extend(processar(pdf, a.dia, cfg, cache, cache_path, usar_ia, pasta_ev))

    if dados:
        saida = f"resultado_dia{a.dia}.csv"
        pd.DataFrame(dados).to_csv(saida, index=False, encoding="utf-8-sig")
        print(f"\n{len(dados)} cartões -> {saida} | evidências em ./{pasta_ev}")
        n = TOTAL["chamadas"]
        if n:
            print(f"IA: {n} chamadas | entrada {TOTAL['entrada']} | saída {TOTAL['saida']} | "
                  f"pensamento {TOTAL['pensamento']} | total {TOTAL['total']} | "
                  f"média {TOTAL['total'] // n} tokens/cartão")


if __name__ == "__main__":
    main()