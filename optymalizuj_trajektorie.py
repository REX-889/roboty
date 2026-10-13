"""Optymalizuje kolejnosc wykonania odcinkow i tworzy PDF porownawczy.

Skrypt korzysta z punktow i polaczen z pliku generuj_siatke_a4.py.
Pierwszy odcinek jest wykonywany od P1. Pozostale odcinki moga byc
wykonywane w dowolnej kolejnosci i kierunku. Optymalizacja minimalizuje
sume odcinkow roboczych oraz przejazdow pomiedzy nimi.
"""

from __future__ import annotations

import argparse
import heapq
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas

from generuj_siatke_a4 import POLACZENIA, PUNKTY, rysuj_strzalke


Punkt = tuple[float, float]


@dataclass(frozen=True)
class Prostokat:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def powiekszony(self, margines: float) -> "Prostokat":
        return Prostokat(
            self.xmin - margines,
            self.ymin - margines,
            self.xmax + margines,
            self.ymax + margines,
        )


@dataclass(frozen=True)
class OdcinekPrzeszkody:
    a: Punkt
    b: Punkt


Przeszkoda = Prostokat | OdcinekPrzeszkody


@dataclass
class Przejazd:
    punkt_a: int
    punkt_b: int
    droga: list[Punkt]
    dystans: float


@dataclass
class Wynik:
    wykonanie: list[tuple[int, int]]
    przejazdy: list[Przejazd]
    kolejnosc_punktow: list[int]
    dystans_odcinkow: float
    dystans_przejazdow: float

    @property
    def dystans_calkowity(self) -> float:
        return self.dystans_odcinkow + self.dystans_przejazdow


def dystans(a: Punkt, b: Punkt) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def przecina_prostokat(a: Punkt, b: Punkt, r: Prostokat) -> bool:
    """Zwraca True, gdy odcinek przechodzi przez wnetrze prostokata."""
    eps = 1e-7
    xmin, ymin = r.xmin + eps, r.ymin + eps
    xmax, ymax = r.xmax - eps, r.ymax - eps
    if xmin >= xmax or ymin >= ymax:
        return False

    dx, dy = b[0] - a[0], b[1] - a[1]
    t_min, t_max = 0.0, 1.0
    for p, q in (
        (-dx, a[0] - xmin),
        (dx, xmax - a[0]),
        (-dy, a[1] - ymin),
        (dy, ymax - a[1]),
    ):
        if abs(p) < eps:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t_min = max(t_min, t)
        else:
            t_max = min(t_max, t)
        if t_min > t_max:
            return False
    return True


def orientacja(a: Punkt, b: Punkt, c: Punkt) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def punkt_na_odcinku(a: Punkt, b: Punkt, p: Punkt, eps: float = 1e-8) -> bool:
    return (
        abs(orientacja(a, b, p)) <= eps
        and min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def przecina_odcinek(a: Punkt, b: Punkt, przeszkoda: OdcinekPrzeszkody) -> bool:
    """Sprawdza przeciecie lub dotkniecie liniowej przeszkody."""
    c, d = przeszkoda.a, przeszkoda.b
    o1, o2 = orientacja(a, b, c), orientacja(a, b, d)
    o3, o4 = orientacja(c, d, a), orientacja(c, d, b)
    eps = 1e-8
    if o1 * o2 < -eps and o3 * o4 < -eps:
        return True
    return (
        punkt_na_odcinku(a, b, c)
        or punkt_na_odcinku(a, b, d)
        or punkt_na_odcinku(c, d, a)
        or punkt_na_odcinku(c, d, b)
    )


def kolizja(a: Punkt, b: Punkt, przeszkoda: Przeszkoda) -> bool:
    if isinstance(przeszkoda, Prostokat):
        return przecina_prostokat(a, b, przeszkoda)
    return przecina_odcinek(a, b, przeszkoda)


def punkty_objazdu(przeszkoda: Przeszkoda, luz: float) -> list[Punkt]:
    if isinstance(przeszkoda, Prostokat):
        obrys = przeszkoda.powiekszony(luz)
        return [
            (obrys.xmin, obrys.ymin),
            (obrys.xmin, obrys.ymax),
            (obrys.xmax, obrys.ymin),
            (obrys.xmax, obrys.ymax),
        ]

    ax, ay = przeszkoda.a
    bx, by = przeszkoda.b
    dlugosc = dystans(przeszkoda.a, przeszkoda.b)
    ux, uy = (bx - ax) / dlugosc, (by - ay) / dlugosc
    nx, ny = -uy, ux
    return [
        (ax - ux * luz + nx * luz, ay - uy * luz + ny * luz),
        (ax - ux * luz - nx * luz, ay - uy * luz - ny * luz),
        (bx + ux * luz + nx * luz, by + uy * luz + ny * luz),
        (bx + ux * luz - nx * luz, by + uy * luz - ny * luz),
    ]


def najkrotsza_droga(
    a: Punkt,
    b: Punkt,
    przeszkoda: Przeszkoda | None,
    luz: float = 0.35,
) -> tuple[list[Punkt], float]:
    if a == b:
        return [a], 0.0
    if przeszkoda is None or not kolizja(a, b, przeszkoda):
        return [a, b], dystans(a, b)

    wezly: list[Punkt] = [a, b] + punkty_objazdu(przeszkoda, luz)
    graf: list[list[tuple[int, float]]] = [[] for _ in wezly]
    for i in range(len(wezly)):
        for j in range(i + 1, len(wezly)):
            if not kolizja(wezly[i], wezly[j], przeszkoda):
                koszt = dystans(wezly[i], wezly[j])
                graf[i].append((j, koszt))
                graf[j].append((i, koszt))

    koszty = [math.inf] * len(wezly)
    poprzedni: list[int | None] = [None] * len(wezly)
    koszty[0] = 0.0
    kolejka: list[tuple[float, int]] = [(0.0, 0)]
    while kolejka:
        koszt, u = heapq.heappop(kolejka)
        if koszt > koszty[u] + 1e-12:
            continue
        if u == 1:
            break
        for v, waga in graf[u]:
            nowy = koszt + waga
            if nowy + 1e-12 < koszty[v]:
                koszty[v] = nowy
                poprzedni[v] = u
                heapq.heappush(kolejka, (nowy, v))

    if math.isinf(koszty[1]):
        raise RuntimeError("Nie znaleziono drogi omijajacej przeszkode.")

    indeksy = []
    obecny: int | None = 1
    while obecny is not None:
        indeksy.append(obecny)
        obecny = poprzedni[obecny]
    indeksy.reverse()
    return [wezly[i] for i in indeksy], koszty[1]


def konce_odcinka(numer: int, kierunek: int) -> tuple[int, int]:
    a, b = POLACZENIA[numer]
    return (a, b) if kierunek == 0 else (b, a)


def optymalizuj(przeszkoda: Przeszkoda | None = None) -> Wynik:
    """Dokladne DP po kolejnosci i kierunku szesciu odcinkow."""
    liczba = len(POLACZENIA)
    if liczba != 6:
        raise ValueError("Algorytm oczekuje dokladnie 6 odcinkow.")

    for a, b in POLACZENIA:
        if przeszkoda and kolizja(PUNKTY[a], PUNKTY[b], przeszkoda):
            raise ValueError("Przeszkoda przecina obowiazkowy odcinek roboczy.")

    # Trasa zaczyna sie od P1 i pierwszego odcinka P1 -> P2.
    pierwszy = (0, 0)
    a0, b0 = konce_odcinka(*pierwszy)
    stan: dict[tuple[int, int, int], tuple[float, list[tuple[int, int]]]] = {
        (1, 0, 0): (dystans(PUNKTY[a0], PUNKTY[b0]), [pierwszy])
    }

    for _ in range(1, liczba):
        nowy_stan: dict[
            tuple[int, int, int], tuple[float, list[tuple[int, int]]]
        ] = {}
        for (maska, ostatni, kierunek), (koszt, sekwencja) in stan.items():
            _, obecny_koniec = konce_odcinka(ostatni, kierunek)
            for nastepny in range(liczba):
                if maska & (1 << nastepny):
                    continue
                for nowy_kierunek in (0, 1):
                    start, koniec = konce_odcinka(nastepny, nowy_kierunek)
                    _, przejazd = najkrotsza_droga(
                        PUNKTY[obecny_koniec], PUNKTY[start], przeszkoda
                    )
                    nowy_koszt = (
                        koszt
                        + przejazd
                        + dystans(PUNKTY[start], PUNKTY[koniec])
                    )
                    klucz = (
                        maska | (1 << nastepny),
                        nastepny,
                        nowy_kierunek,
                    )
                    if klucz not in nowy_stan or nowy_koszt < nowy_stan[klucz][0]:
                        nowy_stan[klucz] = (
                            nowy_koszt,
                            sekwencja + [(nastepny, nowy_kierunek)],
                        )
        stan = nowy_stan

    _, wykonanie = min(stan.values(), key=lambda element: element[0])
    przejazdy: list[Przejazd] = []
    kolejnosc: list[int] = []
    suma_odcinkow = 0.0

    for pozycja, (numer, kierunek) in enumerate(wykonanie):
        start, koniec = konce_odcinka(numer, kierunek)
        if pozycja == 0:
            kolejnosc.append(start)
        else:
            _, poprzedni_koniec = konce_odcinka(*wykonanie[pozycja - 1])
            droga, dlugosc = najkrotsza_droga(
                PUNKTY[poprzedni_koniec], PUNKTY[start], przeszkoda
            )
            if dlugosc > 1e-9:
                przejazdy.append(
                    Przejazd(poprzedni_koniec, start, droga, dlugosc)
                )
                if kolejnosc[-1] != start:
                    kolejnosc.append(start)
        kolejnosc.append(koniec)
        suma_odcinkow += dystans(PUNKTY[start], PUNKTY[koniec])

    return Wynik(
        wykonanie=wykonanie,
        przejazdy=przejazdy,
        kolejnosc_punktow=kolejnosc,
        dystans_odcinkow=suma_odcinkow,
        dystans_przejazdow=sum(p.dystans for p in przejazdy),
    )


def odleglosc_od_odcinka(p: Punkt, a: Punkt, b: Punkt) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    mianownik = dx * dx + dy * dy
    if mianownik == 0:
        return dystans(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / mianownik))
    rzut = (a[0] + t * dx, a[1] + t * dy)
    return dystans(p, rzut)


def wybierz_przeszkode(
    wynik: Wynik,
    typ: str = "prostokat",
) -> tuple[Przeszkoda, Przejazd]:
    """Umieszcza wybrany typ przeszkody na optymalnym przejezdzie."""
    for przejazd in sorted(wynik.przejazdy, key=lambda p: p.dystans, reverse=True):
        a, b = PUNKTY[przejazd.punkt_a], PUNKTY[przejazd.punkt_b]
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if typ == "odcinek":
            dlugosc = dystans(a, b)
            ux, uy = (b[0] - a[0]) / dlugosc, (b[1] - a[1]) / dlugosc
            nx, ny = -uy, ux
            for polowa in (1.8, 1.5, 1.2):
                kandydat_liniowy = OdcinekPrzeszkody(
                    (cx - nx * polowa, cy - ny * polowa),
                    (cx + nx * polowa, cy + ny * polowa),
                )
                if any(
                    not (0.5 < wsp < limit)
                    for punkt in (kandydat_liniowy.a, kandydat_liniowy.b)
                    for wsp, limit in zip(punkt, (18.5, 26.5))
                ):
                    continue
                if any(
                    odleglosc_od_odcinka(p, kandydat_liniowy.a, kandydat_liniowy.b)
                    < 0.4
                    for p in PUNKTY
                ):
                    continue
                if any(
                    przecina_odcinek(PUNKTY[i], PUNKTY[j], kandydat_liniowy)
                    for i, j in POLACZENIA
                ):
                    continue
                if przecina_odcinek(a, b, kandydat_liniowy):
                    return kandydat_liniowy, przejazd
            continue

        for polowa in (1.2, 1.0, 0.8):
            kandydat = Prostokat(
                cx - polowa,
                cy - polowa,
                cx + polowa,
                cy + polowa,
            )
            if not (0.5 < kandydat.xmin and kandydat.xmax < 18.5):
                continue
            if not (0.5 < kandydat.ymin and kandydat.ymax < 26.5):
                continue
            if any(
                kandydat.xmin - 0.2 <= x <= kandydat.xmax + 0.2
                and kandydat.ymin - 0.2 <= y <= kandydat.ymax + 0.2
                for x, y in PUNKTY
            ):
                continue
            if any(
                przecina_prostokat(PUNKTY[i], PUNKTY[j], kandydat)
                for i, j in POLACZENIA
            ):
                continue
            if przecina_prostokat(a, b, kandydat):
                return kandydat, przejazd
    raise RuntimeError(f"Nie udalo sie bezpiecznie umiescic przeszkody: {typ}.")


def rysuj_siatke(pdf: canvas.Canvas) -> tuple[float, float]:
    szerokosc, wysokosc = A4
    ox = oy = 10 * mm
    x_koniec, y_koniec = szerokosc - 10 * mm, wysokosc - 10 * mm

    pdf.setStrokeColor(Color(0.82, 0.86, 0.90))
    pdf.setLineWidth(0.25)
    x = ox
    while x <= x_koniec:
        pdf.line(x, oy, x, y_koniec)
        x += 5 * mm
    y = oy
    while y <= y_koniec:
        pdf.line(ox, y, x_koniec, y)
        y += 5 * mm

    pdf.setStrokeColor(Color(0.52, 0.58, 0.64))
    pdf.setLineWidth(0.7)
    x = ox
    while x <= x_koniec:
        pdf.line(x, oy, x, y_koniec)
        x += cm
    y = oy
    while y <= y_koniec:
        pdf.line(ox, y, x_koniec, y)
        y += cm

    pdf.setStrokeColor(Color(0.18, 0.22, 0.27))
    pdf.setFillColor(Color(0.18, 0.22, 0.27))
    pdf.setLineWidth(1.15)
    rysuj_strzalke(pdf, ox, oy, x_koniec, oy)
    rysuj_strzalke(pdf, ox, oy, ox, y_koniec)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(x_koniec - 1.5 * mm, oy + 2.5 * mm, "X")
    pdf.drawString(ox + 2.5 * mm, y_koniec - 3.5 * mm, "Y")
    return ox, oy


def rysuj_mape(
    pdf: canvas.Canvas,
    wynik: Wynik,
    podpis: str,
    przeszkoda: Przeszkoda | None = None,
) -> None:
    ox, oy = rysuj_siatke(pdf)

    if przeszkoda:
        pdf.setStrokeColor(Color(0.65, 0.08, 0.08))
        if isinstance(przeszkoda, Prostokat):
            pdf.setFillColor(Color(0.93, 0.63, 0.58, alpha=0.75))
            pdf.setLineWidth(1.2)
            pdf.rect(
                ox + przeszkoda.xmin * cm,
                oy + przeszkoda.ymin * cm,
                (przeszkoda.xmax - przeszkoda.xmin) * cm,
                (przeszkoda.ymax - przeszkoda.ymin) * cm,
                stroke=1,
                fill=1,
            )
            etykieta_x = przeszkoda.xmin
            etykieta_y = przeszkoda.ymax + 0.2
        else:
            pdf.setLineWidth(4.0)
            pdf.line(
                ox + przeszkoda.a[0] * cm,
                oy + przeszkoda.a[1] * cm,
                ox + przeszkoda.b[0] * cm,
                oy + przeszkoda.b[1] * cm,
            )
            etykieta_x = min(przeszkoda.a[0], przeszkoda.b[0])
            etykieta_y = max(przeszkoda.a[1], przeszkoda.b[1]) + 0.2
        pdf.setFillColor(Color(0.55, 0.03, 0.03))
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(
            ox + etykieta_x * cm,
            oy + etykieta_y * cm,
            "PRZESZKODA",
        )

    # Przejazdy pomocnicze sa rysowane jako linie przerywane.
    pdf.setStrokeColor(Color(0.88, 0.38, 0.05))
    pdf.setLineWidth(1.4)
    pdf.setDash(5, 3)
    for przejazd in wynik.przejazdy:
        for a, b in zip(przejazd.droga, przejazd.droga[1:]):
            pdf.line(ox + a[0] * cm, oy + a[1] * cm, ox + b[0] * cm, oy + b[1] * cm)
    pdf.setDash()

    # Obowiazkowe odcinki robocze.
    pdf.setStrokeColor(Color(0.05, 0.28, 0.55))
    pdf.setLineWidth(1.9)
    for i, j in POLACZENIA:
        a, b = PUNKTY[i], PUNKTY[j]
        pdf.line(ox + a[0] * cm, oy + a[1] * cm, ox + b[0] * cm, oy + b[1] * cm)

    for indeks, (x, y) in enumerate(PUNKTY, start=1):
        px, py = ox + x * cm, oy + y * cm
        pdf.setFillColor(white)
        pdf.setStrokeColor(black)
        pdf.setLineWidth(0.8)
        pdf.circle(px, py, 1.4 * mm, stroke=1, fill=1)
        pdf.setFillColor(black)
        pdf.setFont("Helvetica-Bold", 8)
        if indeks % 2 == 1:
            pdf.drawRightString(px - 2.5 * mm, py + 2.5 * mm, f"P{indeks}")
        else:
            pdf.drawString(px + 2.5 * mm, py + 2.5 * mm, f"P{indeks}")

    pdf.setFillColor(Color(0.18, 0.22, 0.27))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(10 * mm, 4.5 * mm, podpis)
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(
        A4[0] - 10 * mm,
        4.5 * mm,
        "niebieski: praca | pomaranczowy: przejazd",
    )
    pdf.showPage()


def nazwa_punktu(indeks: int) -> str:
    return f"P{indeks + 1}"


def tekst_kolejnosci(wynik: Wynik) -> str:
    return " -> ".join(nazwa_punktu(i) for i in wynik.kolejnosc_punktow)


def dopisz_zawijany(
    pdf: canvas.Canvas,
    tekst: str,
    x: float,
    y: float,
    szerokosc: int = 92,
    krok: float = 5 * mm,
) -> float:
    for wiersz in textwrap.wrap(tekst, width=szerokosc):
        pdf.drawString(x, y, wiersz)
        y -= krok
    return y


def rysuj_notatki(
    pdf: canvas.Canvas,
    bez: Wynik,
    z: Wynik,
    przeszkoda: Przeszkoda,
    blokowany: Przejazd,
) -> None:
    lewy = 18 * mm
    y = A4[1] - 18 * mm
    pdf.setFillColor(black)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(lewy, y, "NOTATKI - OPTYMALIZACJA TRAJEKTORII")
    y -= 11 * mm

    pdf.setFont("Helvetica", 9)
    pdf.drawString(lewy, y, "Jednostka odleglosci: 1 cm (10 mm robota)")
    y -= 6 * mm
    pdf.drawString(lewy, y, "Start: P1. Pierwszy odcinek: P1 - P2.")
    y -= 10 * mm

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(lewy, y, "Odcinki robocze:")
    y -= 6 * mm
    pdf.setFont("Helvetica", 9)
    for numer, (a, b) in enumerate(POLACZENIA, start=1):
        dlugosc = dystans(PUNKTY[a], PUNKTY[b])
        pdf.drawString(
            lewy,
            y,
            f"S{numer}: {nazwa_punktu(a)} - {nazwa_punktu(b)} = {dlugosc:.2f} cm",
        )
        y -= 5 * mm
    pdf.drawString(lewy, y, f"Suma odcinkow: {bez.dystans_odcinkow:.2f} cm")
    y -= 10 * mm

    for tytul, wynik in (
        ("BEZ PRZESZKODY", bez),
        ("Z PRZESZKODA", z),
    ):
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(lewy, y, tytul)
        y -= 6 * mm
        pdf.setFont("Helvetica", 9)
        y = dopisz_zawijany(
            pdf,
            "Kolejnosc punktow: " + tekst_kolejnosci(wynik),
            lewy,
            y,
        )
        pdf.drawString(lewy, y, "Przejazdy pomocnicze:")
        y -= 5 * mm
        for przejazd in wynik.przejazdy:
            objazd = " (objazd)" if len(przejazd.droga) > 2 else ""
            pdf.drawString(
                lewy + 5 * mm,
                y,
                f"{nazwa_punktu(przejazd.punkt_a)} -> "
                f"{nazwa_punktu(przejazd.punkt_b)}: "
                f"{przejazd.dystans:.2f} cm{objazd}",
            )
            y -= 5 * mm
        pdf.drawString(
            lewy,
            y,
            f"Suma przejazdow: {wynik.dystans_przejazdow:.2f} cm",
        )
        y -= 5 * mm
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(
            lewy,
            y,
            f"Calkowita trasa: {wynik.dystans_calkowity:.2f} cm",
        )
        y -= 10 * mm

    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        lewy,
        y,
        "Przeszkoda zostala ustawiona na pierwotnym przejezdzie "
        f"{nazwa_punktu(blokowany.punkt_a)} -> {nazwa_punktu(blokowany.punkt_b)}.",
    )
    y -= 5 * mm
    if isinstance(przeszkoda, Prostokat):
        opis_przeszkody = (
            f"Prostokat: X={przeszkoda.xmin:.2f}..{przeszkoda.xmax:.2f}, "
            f"Y={przeszkoda.ymin:.2f}..{przeszkoda.ymax:.2f}."
        )
    else:
        opis_przeszkody = (
            f"Odcinek: ({przeszkoda.a[0]:.2f};{przeszkoda.a[1]:.2f}) - "
            f"({przeszkoda.b[0]:.2f};{przeszkoda.b[1]:.2f})."
        )
    pdf.drawString(lewy, y, opis_przeszkody)
    y -= 5 * mm
    pdf.drawString(
        lewy,
        y,
        "Algorytm nie dopuszcza przeciecia przeszkody; objazd sklada sie z odcinkow.",
    )
    pdf.showPage()


def generuj_pdf(
    sciezka: Path,
    typ_przeszkody: str = "prostokat",
) -> tuple[Wynik, Wynik, Przeszkoda]:
    bez = optymalizuj()
    przeszkoda, blokowany = wybierz_przeszkode(bez, typ_przeszkody)
    z = optymalizuj(przeszkoda)

    sciezka.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(sciezka), pagesize=A4)
    pdf.setTitle("Optymalizacja trajektorii manipulatora")
    rysuj_mape(pdf, bez, "OPTYMALNA TRAJEKTORIA - BEZ PRZESZKODY")
    rysuj_mape(pdf, z, "OPTYMALNA TRAJEKTORIA - Z PRZESZKODA", przeszkoda)
    rysuj_notatki(pdf, bez, z, przeszkoda, blokowany)
    pdf.save()
    return bez, z, przeszkoda


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/pdf/optymalizacja_trajektorii_a4.pdf"),
        help="Sciezka wynikowego pliku PDF.",
    )
    parser.add_argument(
        "--typ-przeszkody",
        choices=("prostokat", "odcinek"),
        default="prostokat",
        help="Ksztalt przeszkody umieszczanej na optymalnym przejezdzie.",
    )
    args = parser.parse_args()
    bez, z, przeszkoda = generuj_pdf(args.output, args.typ_przeszkody)
    print("Bez przeszkody:", tekst_kolejnosci(bez))
    print(f"  odcinki={bez.dystans_odcinkow:.2f} cm")
    print(f"  przejazdy={bez.dystans_przejazdow:.2f} cm")
    print(f"  calosc={bez.dystans_calkowity:.2f} cm")
    print("Z przeszkoda:", tekst_kolejnosci(z))
    print(f"  odcinki={z.dystans_odcinkow:.2f} cm")
    print(f"  przejazdy={z.dystans_przejazdow:.2f} cm")
    print(f"  calosc={z.dystans_calkowity:.2f} cm")
    print("Przeszkoda:", przeszkoda)
    print("Utworzono:", args.output.resolve())


if __name__ == "__main__":
    main()
