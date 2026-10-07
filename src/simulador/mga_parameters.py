"""Parâmetro exclusivo do MGA, auditado no MIP 2026.08.21, §§ 4.2.3–4.2.4."""
from decimal import Decimal, InvalidOperation

MIP_URL = ('https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/'
           'thot/arquivos/publicacoes/55422_1804616/MIP-2026-08-21.pdf')


def obter_parametro_mga(ano, entrada=None):
    parametro = {'multiplier': '1.02031208231', 'rate': '0.02031208231',
                 'source': MIP_URL, 'edition': '2026.08.21',
                 'effectiveFrom': '2026-04-22', 'validated': int(ano) == 2026,
                 'meaning': 'Média geométrica do crescimento real do PIB, 2018–2025'}
    if entrada:
        try:
            valor = Decimal(str(entrada.get('value')))
            tipo = entrada.get('unit')
            multiplicador = (1 + valor if tipo == 'rate' else
                             1 + valor / 100 if tipo == 'percent' else valor)
            if tipo not in ('rate', 'percent', 'multiplier') or not multiplicador.is_finite() or multiplicador <= 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError('Informe taxa decimal, taxa percentual ou multiplicador válido para o MGA.') from None
        if multiplicador != Decimal(parametro['multiplier']):
            parametro.update(multiplier=str(multiplicador), rate=str(multiplicador - 1),
                             source=str(entrada.get('source') or 'Hipótese sem fonte verificada'),
                             effectiveFrom=entrada.get('date'), validated=False,
                             meaning='Hipótese informada; parâmetro normativo pendente de validação')
    return parametro
