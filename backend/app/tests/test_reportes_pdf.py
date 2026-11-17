"""C-12 2.2 — exportación PDF (feliz / negocio / borde)."""

from app.domain.reportes.pdf_export import generar_pdf_tabla


def test_pdf_valido_con_titulo_y_marca() -> None:
    pdf = generar_pdf_tabla(
        "Caja", ["concepto", "monto"], [["pago", "10000.00"]], marca="(simulado)"
    )

    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert rb"\(simulado\)" in pdf and b"Caja" in pdf


def test_pdf_sin_marca_no_la_incluye() -> None:
    pdf = generar_pdf_tabla("Turnos", ["a"], [["x"]], marca="")
    assert b"simulado" not in pdf


def test_pdf_pagina_cuando_hay_muchas_filas_y_escapa_parentesis() -> None:
    filas = [[f"fila ({n})"] for n in range(150)]

    pdf = generar_pdf_tabla("Turnos", ["col"], filas, marca="")

    assert pdf.count(b"/Type /Page ") >= 3
    assert b"fila \\(0\\)" in pdf


def test_pdf_sin_filas_sigue_siendo_valido() -> None:
    pdf = generar_pdf_tabla("Vacio", ["a", "b"], [], marca="")
    assert pdf.startswith(b"%PDF-1.4") and b"Sin datos" in pdf
