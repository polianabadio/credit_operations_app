"""Mensagens de orientação; detalhes de exceções ficam no diagnóstico interno."""
import re


def resumir_pendencias_caed(motivos):
    """Agrupa avisos de preenchimento; a memória conserva cada motivo original."""
    mensagens = []
    pagamentos = {}
    rotulos = {'juros_encargos': 'juros e encargos', 'amortizacao': 'amortização',
               'demais_operacoes': 'pagamentos das demais operações'}
    pagamentos_demais_pendentes = any(
        m.get('codigo') == 'PAGAMENTO_AUSENTE_OU_INVALIDO'
        and str(m.get('campo') or '').endswith('.demais_operacoes') for m in motivos)
    for motivo in motivos:
        if motivo.get('codigo') == 'COBERTURA_DEMAIS_AUSENTE' and pagamentos_demais_pendentes:
            continue
        campo = str(motivo.get('campo') or '')
        ano, _, componente = campo.partition('.')
        if (motivo.get('codigo') == 'PAGAMENTO_AUSENTE_OU_INVALIDO'
                and ano.isdigit() and componente in rotulos):
            pagamentos.setdefault(componente, set()).add(int(ano))
            continue
        texto = ('Confirme a cobertura das demais operações, com fonte e data.'
                 if motivo.get('codigo') == 'COBERTURA_DEMAIS_AUSENTE'
                 and not motivo.get('mensagem', '').startswith('Pagamentos obtidos do PVL público')
                 else motivo.get('mensagem', '').strip())
        if texto and texto not in mensagens:
            mensagens.append(texto)
    for componente, anos in pagamentos.items():
        intervalos = []
        inicio = fim = None
        for ano in sorted(anos):
            if fim is not None and ano == fim + 1:
                fim = ano
                continue
            if inicio is not None:
                intervalos.append(str(inicio) if inicio == fim else f'{inicio}–{fim}')
            inicio = fim = ano
        if inicio is not None:
            intervalos.append(str(inicio) if inicio == fim else f'{inicio}–{fim}')
        mensagens.append(f"Faltam informações sobre {rotulos[componente]}: {', '.join(intervalos)}.")
    return ' '.join(mensagens)


def mensagem_erro(erro, alternativa='Não foi possível concluir esta ação. Tente novamente. Se continuar, peça ajuda à equipe responsável pelo aplicativo.'):
    """Preserva validações legíveis sem repassar exceções de infraestrutura."""
    texto = str(erro).strip()
    tecnico = re.search(
        r'cannot import|traceback|sqlalchemy|sqlite|https?://|[a-z]:[\\/]|'
        r'no module|has no attribute|invalid literal|could not convert|'
        r'unsupported operand|unexpected keyword|src\.|SELECT |INSERT |'
        r'connectionpool|timed out|connection refused', texto, re.I)
    if isinstance(erro, ValueError) and texto and not tecnico:
        return texto
    return alternativa
