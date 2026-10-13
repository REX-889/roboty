"""Generuje arkusz A4 z siatka 1 cm / 0,5 cm i 6 odcinkami procesu.

Skala wydruku: 1 jednostka wspolrzednych = 1 cm. Aby zachowac skale,
plik PDF nalezy drukowac w rozmiarze 100% (bez opcji "dopasuj do strony").
Poczatek ukladu znajduje sie w lewym dolnym rogu pola roboczego.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas


# Punkty procesu. Pierwsze 4 tworza trase z 3 odcinkow i zakretami 90 stopni.
PUNKTY: list[tuple[int, int]] = [
    (2, 25),   # P1
    (9, 25),   # P2
    (9, 19),   # P3
    (17, 19),  # P4
    (2, 14),   # P5
    (8, 9),    # P6
    (11, 15),  # P7
    (17, 10),  # P8
    (2, 4),    # P9
    (17, 4),   # P10
]

# Numery punktow sa tu zapisane od zera, zgodnie z indeksami listy PUNKTY.
POLACZENIA: list[tuple[int, int]] = [
    (0, 1),  # P1 - P2
    (1, 2),  # P2 - P3, pierwszy zakret 90 stopni
    (2, 3),  # P3 - P4, drugi zakret 90 stopni
    (4, 5),  # P5 - P6
    (6, 7),  # P7 - P8
    (8, 9),  # P9 - P10
]

# Dwa alternatywne warianty przeszkody wyznaczone dla aktualnego ukladu.
PRZESZKODA_PROSTOKAT = (3.8, 5.3, 6.2, 7.7)
PRZESZKODA_ODCINEK = ((6.15, 5.12), (3.85, 7.88))


def sprawdz_odcinki(
    punkty: list[tuple[int, int]],
    polaczenia: list[tuple[int, int]],
) -> None:
    if len(polaczenia) != 6:
        raise ValueError("Lista musi zawierac dokladnie 6 odcinkow.")
    if any(not isinstance(v, int) for punkt in punkty for v in punkt):
        raise ValueError("Wszystkie wspolrzedne musza byc liczbami calkowitymi.")
    if any(a == b for a, b in polaczenia):
        raise ValueError("Poczatek i koniec odcinka nie moga byc takie same.")
    if any(indeks < 0 or indeks >= len(punkty) for para in polaczenia for indeks in para):
        raise ValueError("Polaczenie odwoluje sie do nieistniejacego punktu.")
    if any(v < 0 for punkt in punkty for v in punkt):
        raise ValueError("Wspolrzedne musza byc dodatnie dla ukladu w rogu kartki.")


def rysuj_strzalke(
    pdf: canvas.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    rozmiar: float = 3 * mm,
) -> None:
    """Rysuje os zakonczona wypelnionym grotem."""
    pdf.line(x1, y1, x2, y2)
    grot = pdf.beginPath()
    if abs(x2 - x1) >= abs(y2 - y1):
        grot.moveTo(x2, y2)
        grot.lineTo(x2 - rozmiar, y2 + rozmiar / 2)
        grot.lineTo(x2 - rozmiar, y2 - rozmiar / 2)
    else:
        grot.moveTo(x2, y2)
        grot.lineTo(x2 - rozmiar / 2, y2 - rozmiar)
        grot.lineTo(x2 + rozmiar / 2, y2 - rozmiar)
    grot.close()
    pdf.drawPath(grot, stroke=1, fill=1)


def generuj_pdf(
    sciezka: Path,
    punkty: list[tuple[int, int]],
    polaczenia: list[tuple[int, int]],
    typ_przeszkody: str = "prostokat",
) -> None:
    sprawdz_odcinki(punkty, polaczenia)
    if typ_przeszkody not in {"prostokat", "odcinek"}:
        raise ValueError("Typ przeszkody musi miec wartosc 'prostokat' albo 'odcinek'.")
    sciezka.parent.mkdir(parents=True, exist_ok=True)

    szerokosc, wysokosc = A4
    pdf = canvas.Canvas(str(sciezka), pagesize=A4)
    pdf.setTitle("Siatka wspolrzednych A4 - 6 odcinkow")

    # Lewy dolny rog drukowalnego pola jest poczatkiem ukladu (0, 0).
    krok = 5 * mm
    margines = 10 * mm
    ox, oy = margines, margines
    x_koniec = szerokosc - margines
    y_koniec = wysokosc - margines

    # Linie pomocnicze co 0,5 cm.
    pdf.setStrokeColor(Color(0.82, 0.86, 0.90))
    pdf.setLineWidth(0.25)
    x = ox
    while x <= x_koniec:
        pdf.line(x, oy, x, y_koniec)
        x += krok
    y = oy
    while y <= y_koniec:
        pdf.line(ox, y, x_koniec, y)
        y += krok

    # Linie glowne co 1 cm.
    pdf.setStrokeColor(Color(0.52, 0.58, 0.64))
    pdf.setLineWidth(0.7)
    krok_cm = 1 * cm
    x = ox
    while x <= x_koniec:
        pdf.line(x, oy, x, y_koniec)
        x += krok_cm
    y = oy
    while y <= y_koniec:
        pdf.line(ox, y, x_koniec, y)
        y += krok_cm

    # Prawoskretny uklad: X w prawo, Y do gory, Z prostopadle do kartki.
    pdf.setStrokeColor(Color(0.18, 0.22, 0.27))
    pdf.setFillColor(Color(0.18, 0.22, 0.27))
    pdf.setLineWidth(1.15)
    rysuj_strzalke(pdf, ox, oy, x_koniec, oy)
    rysuj_strzalke(pdf, ox, oy, ox, y_koniec)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(x_koniec - 1.5 * mm, oy + 2.5 * mm, "X")
    pdf.drawString(ox + 2.5 * mm, y_koniec - 3.5 * mm, "Y")
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(ox + 2.5 * mm, oy + 2.5 * mm, "O(0, 0)")

    # Symbol kropki w okregu oznacza dodatni zwrot osi Z z kartki do obserwatora.
    z_x, z_y = ox + 12 * mm, oy + 8 * mm
    pdf.circle(z_x, z_y, 2.2 * mm, stroke=1, fill=0)
    pdf.circle(z_x, z_y, 0.55 * mm, stroke=0, fill=1)
    pdf.drawString(z_x + 3 * mm, z_y - 1 * mm, "Z")

    # W kazdym pliku wystepuje tylko jeden wybrany wariant przeszkody.
    if typ_przeszkody == "prostokat":
        xmin, ymin, xmax, ymax = PRZESZKODA_PROSTOKAT
        pdf.setFillColor(Color(0.93, 0.63, 0.58, alpha=0.55))
        pdf.setStrokeColor(Color(0.75, 0.12, 0.10))
        pdf.setLineWidth(1.1)
        pdf.rect(
            ox + xmin * cm,
            oy + ymin * cm,
            (xmax - xmin) * cm,
            (ymax - ymin) * cm,
            stroke=1,
            fill=1,
        )
        etykieta = "PRZESZKODA PROSTOKATNA"
    else:
        (ax, ay), (bx, by) = PRZESZKODA_ODCINEK
        pdf.setStrokeColor(Color(0.55, 0.03, 0.03))
        pdf.setLineWidth(4.0)
        pdf.line(ox + ax * cm, oy + ay * cm, ox + bx * cm, oy + by * cm)
        etykieta = "PRZESZKODA LINIOWA"
    pdf.setFillColor(Color(0.55, 0.03, 0.03))
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(ox + 3.8 * cm, oy + 8.1 * cm, etykieta)

    # Pierwsze 3 odcinki tworza trase z dwoma zakretami pod katem prostym.
    pdf.setStrokeColor(Color(0.05, 0.28, 0.55))
    pdf.setLineWidth(1.8)
    for indeks_a, indeks_b in polaczenia:
        x1, y1 = punkty[indeks_a]
        x2, y2 = punkty[indeks_b]
        pdf.line(ox + x1 * cm, oy + y1 * cm, ox + x2 * cm, oy + y2 * cm)

    # Na pierwszej stronie przy punktach sa tylko ich nazwy.
    for indeks, (x, y) in enumerate(punkty, start=1):
        px, py = ox + x * cm, oy + y * cm
        nazwa = f"P{indeks}"
        pdf.setFillColor(white)
        pdf.setStrokeColor(black)
        pdf.setLineWidth(0.8)
        pdf.circle(px, py, 1.4 * mm, stroke=1, fill=1)
        pdf.setFillColor(black)
        pdf.setFont("Helvetica-Bold", 8)
        if indeks % 2 == 1:
            pdf.drawRightString(px - 2.5 * mm, py + 2.5 * mm, nazwa)
        else:
            pdf.drawString(px + 2.5 * mm, py + 2.5 * mm, nazwa)

    # Koniec pierwszej kartki: tylko tablica robocza.
    pdf.showPage()

    # Druga kartka: zwykle notatki pomocnicze bez siatki.
    lewy = 20 * mm
    gora = wysokosc - 20 * mm
    pdf.setFillColor(black)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(lewy, gora, "NOTATKI POMOCNICZE")

    pdf.setFont("Helvetica", 10)
    y = gora - 12 * mm
    pdf.drawString(lewy, y, "Skala: 1 jednostka = 1 cm")
    y -= 6 * mm
    pdf.drawString(lewy, y, "Drukowanie tablicy: rozmiar 100%, bez dopasowania do strony")
    y -= 6 * mm
    pdf.drawString(lewy, y, "Osie: X w prawo, Y do gory, Z prostopadle do kartki")

    y -= 12 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(lewy, y, "Przeszkoda:")
    pdf.setFont("Helvetica", 10)
    y -= 7 * mm
    if typ_przeszkody == "prostokat":
        pdf.drawString(lewy, y, "Prostokat: X=3.80..6.20, Y=5.30..7.70")
    else:
        pdf.drawString(lewy, y, "Odcinek: (6.15;5.12) - (3.85;7.88)")

    y -= 12 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(lewy, y, "Punkty:")
    pdf.setFont("Helvetica", 10)
    y -= 7 * mm
    for indeks, (x, y_wsp) in enumerate(punkty, start=1):
        pdf.drawString(lewy, y, f"P{indeks}({x};{y_wsp})")
        y -= 7 * mm

    y -= 7 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(lewy, y, "Odcinki:")
    pdf.setFont("Helvetica", 10)
    y -= 7 * mm
    for numer, (indeks_a, indeks_b) in enumerate(polaczenia, start=1):
        pdf.drawString(lewy, y, f"{numer}. P{indeks_a + 1} - P{indeks_b + 1}")
        y -= 7 * mm

    y -= 5 * mm
    pdf.drawString(
        lewy,
        y,
        "Odcinki 1-3 tworza wspolna trase z dwoma zakretami 90 stopni.",
    )

    pdf.showPage()
    pdf.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/pdf"),
        help="Katalog dla dwoch wynikowych plikow PDF.",
    )
    args = parser.parse_args()
    warianty = (
        ("prostokat", "siatka_punkty_przeszkoda_prostokat_a4.pdf"),
        ("odcinek", "siatka_punkty_przeszkoda_odcinek_a4.pdf"),
    )
    for typ, nazwa in warianty:
        wynik = args.output_dir / nazwa
        generuj_pdf(wynik, PUNKTY, POLACZENIA, typ)
        print(f"Utworzono: {wynik.resolve()}")


if __name__ == "__main__":
    main()
