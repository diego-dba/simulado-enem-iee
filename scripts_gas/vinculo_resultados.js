function normalizarTexto(texto) {
  if (!texto) return "";
  return texto.toString()
              .toUpperCase()
              .normalize("NFD")
              .replace(/[\u0300-\u036f]/g, "") 
              .trim();
}

function processarResultadosDia1() {
  const plan = SpreadsheetApp.getActiveSpreadsheet();
  const abaBanco = plan.getSheetByName("Banco_Geral");
  const abaPython = plan.getSheetByName("Dados_Python_D1");
  const abaResultado = plan.getSheetByName("Resultado_Geral");

  const dadosBanco = abaBanco.getDataRange().getValues();
  const dadosPython = abaPython.getDataRange().getValues();
  
  // Pega os dados atuais da Resultado_Geral para não apagar turmas antigas
  const dadosResultadoAtual = abaResultado.getDataRange().getValues();

  const cartoesLidos = {};
  const turmasPresentesNoCSV = {}; // Rastreador de turmas "cobaias"
  
  // 1. Organiza os cartões lidos
  for (let i = 1; i < dadosPython.length; i++) {
    let linha = dadosPython[i];
    let turma = linha[3].toString(); 
    let nomeIA = normalizarTexto(linha[4]); 
    let acertos = linha[7]; 

    if (!cartoesLidos[turma]) {
      cartoesLidos[turma] = [];
    }
    cartoesLidos[turma].push({ nomeLido: nomeIA, acertos: acertos, vinculado: false });
    turmasPresentesNoCSV[turma] = true; // Marca que essa turma tem dados novos
  }

  const dadosFinais = [];

  // 2. Monta o resultado baseado no Banco Oficial
  for (let i = 1; i < dadosBanco.length; i++) {
    let turno = dadosBanco[i][0];
    let turmaOficial = dadosBanco[i][1].toString();
    let matricula = dadosBanco[i][2];
    let nomeOficial = normalizarTexto(dadosBanco[i][3]);

    // Se a turma deste aluno NÃO foi processada hoje, mantemos os dados que já estavam lá
    if (!turmasPresentesNoCSV[turmaOficial]) {
      let linhaAntiga = dadosResultadoAtual[i] || [turno, turmaOficial, matricula, dadosBanco[i][3], "", "", ""];
      dadosFinais.push(linhaAntiga);
      continue;
    }

    // Se a turma FOI processada (ex: 305), fazemos o match seguro
    let acertosAluno = "";
    let situacao = "Faltou"; 

    if (cartoesLidos[turmaOficial]) {
      let cartoesDaTurma = cartoesLidos[turmaOficial];

      for (let j = 0; j < cartoesDaTurma.length; j++) {
        let cartao = cartoesDaTurma[j];
        if (cartao.vinculado) continue; 

        // MATCH SEGURO: Verifica se o Nome e Sobrenome batem exatamente
        let oficialWords = nomeOficial.split(" ");
        let lidoWords = cartao.nomeLido.split(" ");
        
        let matchPerfeito = (nomeOficial === cartao.nomeLido);
        let matchPrimeirosNomes = (lidoWords.length > 1 && oficialWords.length > 1) && 
                                  (lidoWords[0] === oficialWords[0] && lidoWords[1] === oficialWords[1]);

        if (matchPerfeito || matchPrimeirosNomes) {
          acertosAluno = cartao.acertos;
          situacao = "Presente";
          cartao.vinculado = true; 
          break; 
        }
      }
    }

    dadosFinais.push([turno, turmaOficial, matricula, dadosBanco[i][3], acertosAluno, "", situacao]);
  }

  // 3. Injeta na planilha
  if (abaResultado.getLastRow() > 1) {
    abaResultado.getRange(2, 1, abaResultado.getLastRow() - 1, 7).clearContent();
  }
  if (dadosFinais.length > 0) {
    abaResultado.getRange(2, 1, dadosFinais.length, 7).setValues(dadosFinais);
  }

  SpreadsheetApp.getUi().alert("Dia 1 consolidado! Somente as turmas atualizadas no CSV foram modificadas.");
}