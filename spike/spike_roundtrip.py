"""Spike 1: round-trip LibreOffice no arquivo Hias real (somente abrir e salvar)."""
import os, sys, subprocess, time, uno
from com.sun.star.beans import PropertyValue

def _prop(name, value):
    p = PropertyValue(); p.Name = name; p.Value = value
    return p

ENTRADA = "/home/apppf/spike/Posição Financeira Hias.xlsx"
SAIDA = "/home/apppf/spike/spike_roundtrip.xlsx"

# Sobe um soffice headless dedicado ao teste
proc = subprocess.Popen([
    "soffice", "--headless", "--invisible", "--norestore", "--nologo",
    f"-env:UserInstallation=file:///tmp/lo_spike",
    "--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ServiceManager",
])
time.sleep(15)
try:
    localContext = uno.getComponentContext()
    resolver = localContext.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", localContext)
    ctx = resolver.resolve(
        "uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL(
        "file://" + ENTRADA, "_blank", 0,
        (_prop("Hidden", True), _prop("ReadOnly", False)))
    doc.storeToURL("file://" + SAIDA,
                   (_prop("FilterName", "Calc MS Excel 2007 XML"),))
    doc.close(False)
    print("ROUNDTRIP OK ->", SAIDA)
finally:
    proc.terminate(); proc.wait()
