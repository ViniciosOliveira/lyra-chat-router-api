# Pendências técnicas

## Gate obrigatório antes do próximo deploy

- Criar CI no repositório para executar lint, compilação e a suíte de testes em ambiente limpo.
- Corrigir os cinco arquivos legados baseados em `FastAPI TestClient` que travam durante a requisição e hoje atingem timeout sem produzir assertion.
- Tornar a suíte integral finita e verde no CI. Até isso ocorrer, nenhum novo deploy do Router pode ser aprovado apenas por testes focados ou smokes de runtime.

Esta dívida foi aceita excepcionalmente no deploy do shadow da DM do sponsor em 2026-09-10. A exceção não se estende ao deploy seguinte.
