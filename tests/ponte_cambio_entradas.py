"""Conversor real para o teste de interface, com câmbio de mercado fictício."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.simulador.cambio import converter_entradas,registrar_cotacao_contratual
entrada=json.load(sys.stdin)
def ref(id):
    return id if id=='BRL' or id.startswith('manual:') else registrar_cotacao_contratual(id,'5')['id']
try:
    print(json.dumps(dict(status='sucesso',**converter_entradas(entrada['valores'],ref(entrada['origem']),ref(entrada['destino']),entrada.get('conciliar',False)))))
except ValueError as exc:
    print(json.dumps(dict(status='erro',mensagem=str(exc))))
