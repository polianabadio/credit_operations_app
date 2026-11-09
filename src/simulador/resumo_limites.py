"""Demonstrações complementares do cenário, sem substituir regras publicadas."""
from decimal import Decimal, localcontext
from .dcl import normalizar
from .servico_divida import decimal_nao_negativo


def demonstrar_dcl(ano, registros, principal, outras=None, cobertura=False, fonte=None):
    linhas=[r for r in registros if r['exercicio']==ano]
    periodo=max((r['periodo'] for r in linhas),default=None)
    memoria={'ano':ano,'periodo':periodo,'fonte':'SICONFI/RGF-Anexo 02 · GO · Executivo','componentes':{}}
    def unico(prefixo):
        candidatos=[r for r in linhas if r['periodo']==periodo and normalizar(r['conta']).startswith(prefixo)
                    and normalizar(r['coluna'])==normalizar(f'Até o {periodo}º Quadrimestre')]
        memoria['componentes'][prefixo]=[dict(conta=r['conta'],coluna=r['coluna'],valor=str(r['valor']) if r['valor'] is not None else None) for r in candidatos]
        valor=Decimal(str(candidatos[0]['valor'])) if len(candidatos)==1 and candidatos[0]['valor'] is not None else None
        return valor if valor is not None and valor.is_finite() else None
    dcl=unico('DIVIDA CONSOLIDADA LIQUIDA (DCL)')
    rcl=unico('RECEITA CORRENTE LIQUIDA AJUSTADA PARA CALCULO DOS LIMITES DE ENDIVIDAMENTO')
    if outras is not None: outras=decimal_nao_negativo(outras,'Outras operações para DCL')
    principal=decimal_nao_negativo(principal,'Principal')
    with localcontext() as contexto:
        contexto.prec=50
        total=dcl+principal+outras if dcl is not None and outras is not None else None
        percentual=total/rcl*100 if total is not None and rcl is not None and rcl>0 else None
        completo=percentual is not None and cobertura is True and bool(str(fonte or '').strip())
        return dict(tipo='dcl_cenario',limite='200',dcl_publicada=str(dcl) if dcl is not None else None,rcl=str(rcl) if rcl is not None else None,principal=str(principal),outras_operacoes=str(outras) if outras is not None else None,total=str(total) if total is not None else None,percentual=str(percentual) if percentual is not None else None,
            resultado_numerico=None if percentual is None else 'Dentro do limite' if percentual<=200 else 'Acima do limite',
            aprovado=None,estado='CENARIO_INFORMADO' if completo else 'INCONCLUSIVO',cobertura_confirmada=completo,fonte_outras=fonte,memoria_exata=memoria,
            observacao='DCL publicada + valor integral da operação pleiteada + outras operações não incorporadas informadas. Demonstração de cenário separada da avaliação publicada; cobertura, elegibilidade e eventual duplicidade dependem da declaração do usuário.')


def demonstrar_mga(bases, outras_por_ano=None, cobertura=False, fonte=None):
    outras_por_ano=outras_por_ano or {}
    linhas=[]
    with localcontext() as contexto:
        contexto.prec=50
        for base in bases:
            a=base['ano'];rcl=Decimal(str(base['rclProjetada'])) if base.get('rclProjetada') is not None else None
            nova=decimal_nao_negativo(base['liberacaoNovaOperacao'],'Liberação da nova operação')
            outras=outras_por_ano.get(str(a),outras_por_ano.get(a))
            outras=decimal_nao_negativo(outras,'Demais liberações') if outras is not None else None
            teto=rcl*Decimal('.16') if rcl is not None and rcl>0 else None
            total=nova+outras if outras is not None else None
            percentual=total/rcl*100 if total is not None and teto is not None else None
            isolada=nova/rcl*100 if teto is not None else None
            linhas.append(dict(ano=a,nova_operacao=str(nova),demais_liberacoes=str(outras) if outras is not None else None,total=str(total) if total is not None else None,rcl_projetada=str(rcl) if rcl is not None else None,teto=str(teto) if teto is not None else None,percentual=str(percentual) if percentual is not None else None,percentual_nova_operacao=str(isolada) if isolada is not None else None,saldo=str(teto-total) if teto is not None and total is not None else None))
    completo=all(l['percentual'] is not None for l in linhas) and cobertura is True and bool(str(fonte or '').strip())
    excedidos=[l['ano'] for l in linhas if l['percentual'] is not None and Decimal(l['percentual'])>16]
    return dict(tipo='mga_cenario',limite='16',linhas=linhas,aprovado=None,estado='CENARIO_INFORMADO' if completo else 'INCONCLUSIVO',cobertura_confirmada=completo,fonte=fonte,anos_acima=excedidos,
        observacao='Limite anual de 16% da mesma RCL projetada do CAED. Liberações da nova operação sempre apresentadas; valores totais dependem das demais liberações. Ausência não equivale a zero. Demonstração do cenário, sem máximo de contratação validado.')
