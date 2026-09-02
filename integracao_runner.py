"""Executa a integração UNO em subprocesso isolado (soffice próprio + crash seguro)."""
import json, sys, traceback

def main():
    args = json.loads(sys.argv[1])
    import integracao_excel as ie
    ie.processar_fases_2_3_4_hias(
        args["limpo"], args["base"], args["final"],
        args["raiz"], args["saida"], args["wpd"])

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[CRÍTICO] Erro na integração: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
