"""Taxa percentual persistida exclusiva do CAED e conversão em multiplicador."""
from datetime import date
from decimal import Decimal, InvalidOperation
from .database_models import db, ParametroSimulacao

CHAVE_TAXA = 'taxa_percentual_rcl_caed'


def obter_taxa_salva():
    registro = db.session.get(ParametroSimulacao, CHAVE_TAXA) if db.session is not None else None
    return Decimal(registro.valor) if registro else Decimal('2.031208231')

MIP_URL = ('https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/'
           'thot/arquivos/publicacoes/55422_1804616/MIP-2026-08-21.pdf')


def obter_fator_projecao(data_referencia=None):
    """Só resolve a janela de referência comprovada nesta edição de 2026."""
    try:
        referencia = date.fromisoformat(data_referencia)
    except (TypeError, ValueError):
        return None
    if not date(2026, 4, 22) <= referencia <= date(2026, 12, 31):
        return None
    taxa = obter_taxa_salva()
    return {'valor': str(Decimal(1) + taxa / Decimal(100)), 'unidade': 'multiplicador',
            'taxa_percentual': str(taxa), 'taxa_decimal': str(taxa / Decimal(100)),
            'fonte': 'Parâmetro local do usuário', 'edicao': 'Parâmetro armazenado',
            'vigencia_inicio': '2026-04-22', 'vigencia_fim': None,
            'referencia_validada_ate': '2026-12-31',
            'data_referencia': referencia.isoformat(),
            'metodologia': 'Taxa percentual configurada localmente; multiplicador = 1 + taxa/100',
            'limite_validacao': 'Referências fora desta janela exigem fator documentado; sem fallback.'}


def salvar_fator_projecao(valor):
    """Salva a taxa percentual, sem confundir porcentagem com multiplicador."""
    try:
        taxa = Decimal(str(valor).strip().removesuffix('%').strip().replace(',', '.'))
        if not taxa.is_finite() or taxa < 0 or taxa > 100:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError('Informe uma taxa percentual entre 0 e 100.') from None
    if db.session is None:
        raise ValueError('Banco indisponível para salvar o parâmetro.')
    try:
        registro = db.session.get(ParametroSimulacao, CHAVE_TAXA)
        if registro is None:
            registro = ParametroSimulacao(chave=CHAVE_TAXA, valor=str(taxa))
            db.session.add(registro)
        else:
            registro.valor = str(taxa)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return str(taxa)
