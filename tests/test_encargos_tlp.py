from decimal import Decimal
import pytest
from src.simulador.encargos import calcular_encargos


def test_fatores_compostos_com_base_252():
    resultado = calcular_encargos(1000, 0, 7, '3.38', 21, 21)
    esperado = (Decimal('1.07') ** (Decimal(21)/252) *
                Decimal('1.0338') ** (Decimal(21)/252) - 1) * 1000
    assert Decimal(resultado['encargos']) == esperado.quantize(Decimal('.01'))


def test_zero_explicito_e_deflacao():
    assert Decimal(calcular_encargos(1000, 0, 0, 0, 21, 21)['encargos']) == 0
    assert Decimal(calcular_encargos(1000, '-0.5', 0, 0, 21, 21)['encargos']) == -5


@pytest.mark.parametrize('dup,dut', [(22, 21), (1, 0), (1.5, 21)])
def test_dias_invalidos(dup, dut):
    with pytest.raises(ValueError):
        calcular_encargos(1000, 0, 7, '3.38', dup, dut)
