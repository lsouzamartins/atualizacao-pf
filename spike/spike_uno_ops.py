"""Spike 2: as operações do fluxo via UNO na cópia spike_roundtrip.xlsx."""
import subprocess, time, uno
from com.sun.star.beans import PropertyValue
from com.sun.star.sheet.CellFlags import VALUE, FORMATTED, HARDATTR, STYLES, OBJECTS
from com.sun.star.table.CellContentType import FORMULA

def _prop(n, v):
    p = PropertyValue(); p.Name = n; p.Value = v; return p

proc = subprocess.Popen([
    "soffice", "--headless", "--invisible", "--norestore", "--nologo",
    f"-env:UserInstallation=file:///tmp/lo_spike2",
    "--accept=socket,host=127.0.0.1,port=2003;urp;StarOffice.ServiceManager"])
time.sleep(15)
ctx = uno.getComponentContext()
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop",
    uno.getComponentContext())
resolver = smgr.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
rctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2003;urp;StarOffice.ComponentContext")
desktop = rctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", rctx)

doc = desktop.loadComponentFromURL(
    "file:///home/apppf/spike/spike_roundtrip.xlsx", "_blank", 0,
    (_prop("Hidden", True),))
try:
    # (1) deletar linhas na BD2 (equiv. Rows("806:...").Delete())
    bd2 = doc.Sheets.getByName("BD2")
    fim = bd2.Rows.Count  # no arquivo real usar endOfSheet
    print("BD2 rows:", fim)
    # (2) escrever valores + formatos (data e moeda)
    cel = bd2.getCellByPosition(0, 0)
    cel.setString("TESTE")
    # (3) fórmula (colunas R-V da BD1)
    bd1 = doc.Sheets.getByName("BD1")
    bd1.getCellByPosition(17, 1).setFormula('=IF(RIGHT(A2,3)="(R)",L2,0)')
    print("formula:", bd1.getCellByPosition(17, 1).getFormula())
    # (4) tabela estruturada BD_1 (DatabaseRange no LO)
    dbr = doc.DatabaseRanges.getByName("BD_1") if doc.DatabaseRanges.hasByName("BD_1") else None
    print("DatabaseRange BD_1:", dbr, dbr.DataArea.AbsoluteName if dbr else "")
    # (5) pivôs: refresh + ShowDetails
    for nome_aba in ("À Quitar", "Data Entrega"):
        aba = doc.Sheets.getByName(nome_aba)
        dps = aba.DataPilotTables
        print(nome_aba, "pivôs:", [dps.getByIndex(i).Name for i in range(dps.Count)])
        for i in range(dps.Count):
            dp = dps.getByIndex(i)
            dp.refresh()
            for fi in range(dp.RowFields.Count):
                campo = dp.RowFields.getByIndex(fi)
                print("  campo linha:", campo.Name, "itens:", len(campo.Items))
                for j in range(len(campo.Items)):
                    item = campo.Items[j]
                    try:
                        item.ShowDetails = False
                    except Exception as e:
                        print("   ShowDetails erro:", e)
    doc.storeToURL("file:///home/apppf/spike/spike_uno_ops.xlsx",
                   (_prop("FilterName", "Calc MS Excel 2007 XML"),))
    print("UNO OPS OK")
finally:
    doc.close(False); proc.terminate(); proc.wait()
