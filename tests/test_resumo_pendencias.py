from copy import deepcopy

from src.simulador.mensagens import resumir_pendencias_caed


def pagamento(ano, componente='demais_operacoes'):
    return {'codigo': 'PAGAMENTO_AUSENTE_OU_INVALIDO',
            'campo': f'{ano}.{componente}', 'mensagem': f'{componente} de {ano}: dado ausente ou inválido'}


def test_agrupar_vinte_e_um_anos_sem_repeticao():
    motivos = [{'codigo': 'COBERTURA_DEMAIS_AUSENTE', 'mensagem': 'Confirme a cobertura.'}]
    motivos += [pagamento(ano) for ano in range(2026, 2047)]
    original = deepcopy(motivos)
    resumo = resumir_pendencias_caed(motivos)
    assert resumo == 'Faltam informações sobre pagamentos das demais operações: 2026–2046.'
    assert motivos == original


def test_intervalos_separados_nao_incluem_anos_validos():
    resumo = resumir_pendencias_caed([pagamento(a) for a in (2026, 2027, 2030, 2032, 2033)])
    assert '2026–2027, 2030, 2032–2033' in resumo


def test_preserva_diferentes_pendencias_sem_duplicar():
    motivos = [pagamento(2026), pagamento(2026, 'amortizacao'),
               {'codigo': 'RCL_AUSENTE', 'mensagem': 'Receita não disponível.'}]
    resumo = resumir_pendencias_caed(motivos + motivos)
    assert resumo.count('Receita não disponível.') == 1
    assert resumo.count('Faltam informações sobre pagamentos das demais operações') == 1
    assert 'Faltam informações sobre amortização: 2026.' in resumo
