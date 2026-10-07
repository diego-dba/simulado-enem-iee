import cv2
import numpy as np

# 1. Carrega uma imagem de evidência que já existe
caminho_imagem = "evidencias_dia1/dia1_305_p001.jpg" # Ajuste se o nome for diferente
img = cv2.imread(caminho_imagem)

if img is None:
    print(f"Erro: Não achou a imagem em {caminho_imagem}")
    exit()

h, w = img.shape[:2]
r = int(0.012 * w)

# 2. AS COORDENADAS QUE VOCÊ VAI AJUSTAR:
multiplicador_x_ing = 0.345
multiplicador_x_esp = 0.485
multiplicador_y = 0.1246

# Calcula os pixels exatos
x_ing = int(multiplicador_x_ing * w)
x_esp = int(multiplicador_x_esp * w)
y_bolhas = int(multiplicador_y * h)

# 3. Desenha os círculos AZUIS (grossura 4)
cv2.circle(img, (x_ing, y_bolhas), r, (255, 0, 0), 4) # Inglês
cv2.circle(img, (x_esp, y_bolhas), r, (255, 0, 0), 4) # Espanhol

# 4. Salva a imagem para você conferir
cv2.imwrite("teste_calibracao.jpg", img)
print("Imagem 'teste_calibracao.jpg' salva! Abra e veja se os círculos azuis acertaram as bolhas.")