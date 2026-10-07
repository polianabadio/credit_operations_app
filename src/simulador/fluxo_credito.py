"""Limite anual de fluxo de crédito, separado das medições fiscais do RGF.

Os cronogramas são entradas explícitas. Ausência (None) ou ano omitido nunca
equivale a zero; a fonte precisa informar zero para o exercício.
"""

from decimal import Decimal, InvalidOperation


class CreditFlowLimitService:
    def __init__(self, percentual_limite=Decimal('0.16'), percentual_atencao=Decimal('0.14')):
        self.percentual_limite = Decimal(str(percentual_limite))
        self.percentual_atencao = Decimal(str(percentual_atencao))
        if not 0 <= self.percentual_atencao <= self.percentual_limite:
            raise ValueError('O limiar de atenção deve ficar entre zero e o limite legal.')

    @staticmethod
    def _valor(valor):
        if valor is None:
            return None
        try:
            numero = Decimal(str(valor))
        except (InvalidOperation, ValueError):
            raise ValueError('Valor financeiro inválido.') from None
        if not numero.is_finite() or numero < 0:
            raise ValueError('Valor financeiro inválido.')
        return numero

    @classmethod
    def projetar_rcl(cls, rcl_referencia, fator_projecao):
        """Aplica um fator informado pela fonte; não presume fator fiscal."""
        referencia = cls._valor(rcl_referencia)
        fator = cls._valor(fator_projecao)
        return referencia * fator if referencia is not None and fator is not None else None

    @classmethod
    def projetar_rcl_anual(cls, referencia, fator, ano_base, periodo, ano_final):
        """Fator persistido é multiplicador (1 + FA); base no fim do bimestre."""
        rcl, multiplicador = cls._valor(referencia), cls._valor(fator)
        if rcl is None or rcl <= 0 or multiplicador is None or multiplicador <= 0:
            return None
        if not 1 <= int(periodo) <= 6 or int(ano_final) < int(ano_base):
            raise ValueError('Período de projeção inválido.')
        proporcional = multiplicador ** (Decimal(12 - 2 * int(periodo)) / Decimal(12))
        return {ano: rcl * proporcional * multiplicador ** (ano - int(ano_base))
                for ano in range(int(ano_base), int(ano_final) + 1)}

    def avaliar(self, ano, rcl_referencia=None, rcl_projetada=None,
                teto_referencia_publicado=None, liberacoes_contratadas=None,
                liberacoes_nao_contratadas=None, liberacoes_analisadas=None,
                fontes=None):
        """Recebe valores anuais por exercício e devolve somente resultados comprováveis.

        ``rcl_projetada`` e cada grupo de liberações são mapas {ano: valor}.
        A operação analisada é opcional para a posição anterior ao pleito.
        """
        ano = int(ano)
        rcl_ref = self._valor(rcl_referencia)
        teto_ref = self._valor(teto_referencia_publicado)
        anos = {ano}
        for mapa in (rcl_projetada, liberacoes_contratadas,
                     liberacoes_nao_contratadas, liberacoes_analisadas):
            if mapa is not None:
                anos.update(int(chave) for chave in mapa)
        anos = set(range(min(anos), max(anos) + 1))

        linhas = []
        for exercicio in sorted(anos):
            def valor_ano(mapa, exercicio=exercicio):
                if mapa is None:
                    return None
                return self._valor(mapa.get(exercicio, mapa.get(str(exercicio))))

            rcl_proj = valor_ano(rcl_projetada)
            contratadas = valor_ano(liberacoes_contratadas)
            nao_contratadas = valor_ano(liberacoes_nao_contratadas)
            analisada = valor_ano(liberacoes_analisadas)
            teto = rcl_proj * self.percentual_limite if rcl_proj is not None and rcl_proj > 0 else None
            cronogramas_completos = (contratadas is not None and nao_contratadas is not None
                                    and (liberacoes_analisadas is None or analisada is not None))
            completos = teto is not None and cronogramas_completos
            mga = (contratadas + nao_contratadas
                   + (analisada if liberacoes_analisadas is not None else Decimal(0))
                   if cronogramas_completos else None)
            percentual = mga / rcl_proj if completos else None
            status = ('comprometimento_nao_disponivel' if percentual is None else
                      'acima_do_limite' if percentual > self.percentual_limite else
                      'proximo_ao_limite' if percentual >= self.percentual_atencao else
                      'dentro_do_limite')
            linhas.append({
                'ano': exercicio,
                'rclProjetada': float(rcl_proj) if rcl_proj is not None else None,
                'tetoAnual': float(teto) if teto is not None else None,
                'liberacoesContratadas': float(contratadas) if contratadas is not None else None,
                'liberacoesNaoContratadas': float(nao_contratadas) if nao_contratadas is not None else None,
                'liberacaoOperacaoAnalisada': float(analisada) if analisada is not None else None,
                'mga': float(mga) if mga is not None else None,
                'percentualMgaRcl': float(percentual * 100) if percentual is not None else None,
                'mgaRcl': float(percentual) if percentual is not None else None,
                'limitUsage': float(percentual / self.percentual_limite) if percentual is not None else None,
                'scheduledDisbursements': float(contratadas + nao_contratadas) if contratadas is not None and nao_contratadas is not None else None,
                'requestedOperation': float(analisada) if analisada is not None else (0 if liberacoes_analisadas is None else None),
                'situacao': 'Projeção indisponível' if percentual is None else 'Não Enquadrado' if percentual > self.percentual_limite else 'Enquadrado',
                'margemEstimada': float(teto - mga) if completos else None,
                'dadosCompletos': completos,
                'status': status,
            })

        atual = next(linha for linha in linhas if linha['ano'] == ano)
        completos = all(linha['dadosCompletos'] for linha in linhas)
        excedidos = [linha['ano'] for linha in linhas if linha['status'] == 'acima_do_limite']
        critico = max(linhas, key=lambda linha: linha['mgaRcl']) if completos else None
        return {
            'globalStatus': 'Não Enquadrado' if excedidos else 'Enquadrado' if completos else 'Projeção indisponível',
            'dataAvailability': completos,
            'criticalYear': critico['ano'] if critico else None,
            'maxMgaRcl': critico['mgaRcl'] if critico else None,
            'maxLimitUsage': critico['limitUsage'] if critico else None,
            'exceededYears': excedidos,
            'limit': float(self.percentual_limite),
            'rows': linhas,
            'ano': ano,
            'rclReferencia': float(rcl_ref) if rcl_ref is not None else None,
            'tetoReferencia': float(teto_ref) if teto_ref is not None else
                              float(rcl_ref * self.percentual_limite) if rcl_ref is not None else None,
            'percentualLimite': float(self.percentual_limite * 100),
            'percentualAtencao': float(self.percentual_atencao * 100),
            **{chave: valor for chave, valor in atual.items() if chave != 'ano'},
            'exercicios': linhas,
            'fontes': list(fontes or []),
        }
