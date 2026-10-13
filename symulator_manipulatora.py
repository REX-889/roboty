"""Interaktywny emulator ruchu koncowki manipulatora po zadanej trasie.

Jednostka XY i Z: cm. Odcinki niebieskie sa ruchami roboczymi przy Z=0.
Podczas przejazdu jalowego koncowka podnosi sie, jedzie po trasie omijajacej
przeszkode w XY, a nastepnie opuszcza sie przed kolejnym odcinkiem roboczym.
"""

from __future__ import annotations

import argparse
import math
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from generuj_siatke_a4 import (
    POLACZENIA,
    PRZESZKODA_ODCINEK,
    PRZESZKODA_PROSTOKAT,
    PUNKTY,
)
from optymalizuj_trajektorie import (
    OdcinekPrzeszkody,
    Prostokat,
    Wynik,
    najkrotsza_droga,
    optymalizuj,
    tekst_kolejnosci,
)


@dataclass(frozen=True)
class Faza:
    rodzaj: str
    start: tuple[float, float, float]
    koniec: tuple[float, float, float]
    opis: str

    @property
    def dlugosc(self) -> float:
        return math.dist(self.start, self.koniec)


def przeszkoda_z_nazwy(nazwa: str):
    if nazwa == "Prostokat":
        return Prostokat(*PRZESZKODA_PROSTOKAT)
    if nazwa == "Odcinek":
        return OdcinekPrzeszkody(*PRZESZKODA_ODCINEK)
    return None


def zbuduj_fazy(wynik: Wynik, przeszkoda, wysokosc: float) -> list[Faza]:
    fazy: list[Faza] = []
    poprzedni_koniec: int | None = None

    for numer, kierunek in wynik.wykonanie:
        a, b = POLACZENIA[numer]
        start, koniec = (a, b) if kierunek == 0 else (b, a)

        if poprzedni_koniec is not None and poprzedni_koniec != start:
            xy_a = tuple(map(float, PUNKTY[poprzedni_koniec]))
            xy_b = tuple(map(float, PUNKTY[start]))
            droga, _ = najkrotsza_droga(xy_a, xy_b, przeszkoda)
            fazy.append(
                Faza(
                    "podnoszenie",
                    (*xy_a, 0.0),
                    (*xy_a, wysokosc),
                    f"Podnoszenie nad P{poprzedni_koniec + 1}",
                )
            )
            for indeks, (poczatek, cel) in enumerate(zip(droga, droga[1:]), 1):
                fazy.append(
                    Faza(
                        "jalowy",
                        (*poczatek, wysokosc),
                        (*cel, wysokosc),
                        f"Przejazd jalowy P{poprzedni_koniec + 1} -> P{start + 1}"
                        f" ({indeks}/{len(droga) - 1})",
                    )
                )
            fazy.append(
                Faza(
                    "opuszczanie",
                    (*xy_b, wysokosc),
                    (*xy_b, 0.0),
                    f"Opuszczanie nad P{start + 1}",
                )
            )

        p_start = tuple(map(float, PUNKTY[start]))
        p_koniec = tuple(map(float, PUNKTY[koniec]))
        fazy.append(
            Faza(
                "roboczy",
                (*p_start, 0.0),
                (*p_koniec, 0.0),
                f"Ruch roboczy P{start + 1} -> P{koniec + 1}",
            )
        )
        poprzedni_koniec = koniec
    return fazy


class Symulator:
    KOLORY = {
        "roboczy": "#145da0",
        "jalowy": "#e67e22",
        "podnoszenie": "#7d3c98",
        "opuszczanie": "#7d3c98",
    }

    def __init__(self, root: tk.Tk, poczatkowa_przeszkoda: str) -> None:
        self.root = root
        root.title("Emulator koncowki manipulatora KUKA / ABB")
        root.minsize(1040, 720)

        self.typ_przeszkody = tk.StringVar(value=poczatkowa_przeszkoda)
        self.predkosc_pracy = tk.DoubleVar(value=2.0)
        self.predkosc_jalowa = tk.DoubleVar(value=5.0)
        self.predkosc_z = tk.DoubleVar(value=3.0)
        self.wysokosc = tk.DoubleVar(value=5.0)
        self.petla = tk.BooleanVar(value=False)
        self.pokaz_slad = tk.BooleanVar(value=True)

        self.fazy: list[Faza] = []
        self.wynik: Wynik | None = None
        self.przeszkoda = None
        self.indeks_fazy = 0
        self.postep_fazy = 0.0
        self.czas_symulacji = 0.0
        self.uruchomiony = False
        self.ostatni_czas = time.perf_counter()
        self.pozycja = (*map(float, PUNKTY[0]), 0.0)
        self.slad: list[tuple[float, float, str, float]] = []
        self.kat_obrotu = math.radians(-35.0)
        self.kat_widoku = math.radians(28.0)
        self.zoom = 1.0
        self.ostatnia_mysz: tuple[int, int] | None = None

        self._menu()
        self._interfejs()
        self.zastosuj_ustawienia()
        self.root.after(30, self._krok)

    def _menu(self) -> None:
        menu = tk.Menu(self.root)
        sym = tk.Menu(menu, tearoff=False)
        sym.add_command(label="Start", accelerator="F5", command=self.start)
        sym.add_command(label="Pauza / wznow", accelerator="Spacja", command=self.pauza)
        sym.add_command(label="Stop", accelerator="Esc", command=self.stop)
        sym.add_command(label="Reset", accelerator="Ctrl+R", command=self.reset)
        sym.add_separator()
        sym.add_command(label="Zakoncz", command=self.root.destroy)
        menu.add_cascade(label="Symulacja", menu=sym)

        widok = tk.Menu(menu, tearoff=False)
        widok.add_checkbutton(label="Pokaz slad koncowki", variable=self.pokaz_slad, command=self.rysuj)
        menu.add_cascade(label="Widok", menu=widok)

        pomoc = tk.Menu(menu, tearoff=False)
        pomoc.add_command(label="Legenda i sterowanie", command=self.pomoc)
        menu.add_cascade(label="Pomoc", menu=pomoc)
        self.root.config(menu=menu)
        self.root.bind("<F5>", lambda _e: self.start())
        self.root.bind("<space>", lambda _e: self.pauza())
        self.root.bind("<Escape>", lambda _e: self.stop())
        self.root.bind("<Control-r>", lambda _e: self.reset())

    def _interfejs(self) -> None:
        glowny = ttk.Frame(self.root, padding=10)
        glowny.pack(fill="both", expand=True)
        glowny.columnconfigure(0, weight=1)
        glowny.rowconfigure(0, weight=1)

        wykres = ttk.Frame(glowny)
        wykres.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        wykres.columnconfigure(0, weight=1)
        wykres.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            wykres,
            width=720,
            height=680,
            bg="#fbfcfd",
            highlightthickness=1,
            highlightbackground="#aab5bf",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            wykres,
            text="Obrot: przeciagnij lewym przyciskiem | Zoom: rolka myszy",
            anchor="center",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.canvas.bind("<Configure>", lambda _e: self.rysuj())
        self.canvas.bind("<ButtonPress-1>", self._start_obrotu)
        self.canvas.bind("<B1-Motion>", self._obrot_mysza)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "ostatnia_mysz", None))
        self.canvas.bind("<MouseWheel>", self._zoom_mysza)
        self.canvas.bind("<Button-4>", lambda e: self._zoom_linux(1))
        self.canvas.bind("<Button-5>", lambda e: self._zoom_linux(-1))

        panel = ttk.Frame(glowny, width=290)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(1, weight=1)

        ttk.Label(panel, text="PARAMETRY RUCHU", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        self._pole(panel, 1, "Przeszkoda", self.typ_przeszkody, ("Brak", "Prostokat", "Odcinek"))
        self._pole(panel, 2, "Predkosc pracy [cm/s]", self.predkosc_pracy)
        self._pole(panel, 3, "Predkosc jalowa [cm/s]", self.predkosc_jalowa)
        self._pole(panel, 4, "Predkosc osi Z [cm/s]", self.predkosc_z)
        self._pole(panel, 5, "Wysokosc przejazdu Z [cm]", self.wysokosc)
        ttk.Checkbutton(panel, text="Powtarzaj trase", variable=self.petla).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=6
        )
        ttk.Button(panel, text="Zastosuj i przelicz trase", command=self.zastosuj_ustawienia).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(4, 14)
        )

        przyciski = ttk.Frame(panel)
        przyciski.grid(row=8, column=0, columnspan=2, sticky="ew")
        for kolumna, (tekst, komenda) in enumerate(
            (("Start", self.start), ("Pauza", self.pauza), ("Stop", self.stop), ("Reset", self.reset))
        ):
            przyciski.columnconfigure(kolumna, weight=1)
            ttk.Button(przyciski, text=tekst, command=komenda).grid(
                row=0, column=kolumna, padx=2, sticky="ew"
            )

        ttk.Separator(panel).grid(row=9, column=0, columnspan=2, sticky="ew", pady=14)
        self.status = tk.StringVar()
        ttk.Label(panel, textvariable=self.status, justify="left", wraplength=290).grid(
            row=10, column=0, columnspan=2, sticky="nw"
        )
        self.trasa = tk.StringVar()
        ttk.Label(panel, textvariable=self.trasa, justify="left", wraplength=290).grid(
            row=11, column=0, columnspan=2, sticky="nw", pady=(12, 0)
        )

    def _start_obrotu(self, event: tk.Event) -> None:
        self.ostatnia_mysz = (event.x, event.y)

    def _obrot_mysza(self, event: tk.Event) -> None:
        if self.ostatnia_mysz is None:
            return
        poprzedni_x, poprzedni_y = self.ostatnia_mysz
        self.kat_obrotu += (event.x - poprzedni_x) * 0.012
        self.kat_widoku = max(
            math.radians(5),
            min(math.radians(85), self.kat_widoku - (event.y - poprzedni_y) * 0.009),
        )
        self.ostatnia_mysz = (event.x, event.y)
        self.rysuj()

    def _zoom_mysza(self, event: tk.Event) -> None:
        self._zoom_linux(1 if event.delta > 0 else -1)

    def _zoom_linux(self, kierunek: int) -> None:
        self.zoom = max(0.45, min(2.8, self.zoom * (1.12 if kierunek > 0 else 1 / 1.12)))
        self.rysuj()

    def _pole(self, rodzic, wiersz, etykieta, zmienna, wartosci=None) -> None:
        ttk.Label(rodzic, text=etykieta).grid(row=wiersz, column=0, sticky="w", pady=3)
        if wartosci:
            widget = ttk.Combobox(rodzic, textvariable=zmienna, values=wartosci, state="readonly", width=15)
        else:
            widget = ttk.Spinbox(rodzic, textvariable=zmienna, from_=0.1, to=100.0, increment=0.5, width=12)
        widget.grid(row=wiersz, column=1, sticky="ew", padx=(8, 0), pady=3)

    def _parametry_poprawne(self) -> bool:
        try:
            wartosci = (self.predkosc_pracy.get(), self.predkosc_jalowa.get(), self.predkosc_z.get())
            wysokosc = self.wysokosc.get()
        except tk.TclError:
            messagebox.showerror("Bledne dane", "Wpisz prawidlowe wartosci liczbowe.")
            return False
        if any(v <= 0 for v in wartosci) or wysokosc < 0:
            messagebox.showerror("Bledne dane", "Predkosci musza byc dodatnie, a wysokosc nieujemna.")
            return False
        return True

    def zastosuj_ustawienia(self) -> None:
        if not self._parametry_poprawne():
            return
        self.przeszkoda = przeszkoda_z_nazwy(self.typ_przeszkody.get())
        self.wynik = optymalizuj(self.przeszkoda)
        self.fazy = zbuduj_fazy(self.wynik, self.przeszkoda, self.wysokosc.get())
        self.trasa.set(
            "Kolejnosc:\n" + tekst_kolejnosci(self.wynik)
            + f"\n\nOdcinki robocze: {self.wynik.dystans_odcinkow:.2f} cm"
            + f"\nPrzejazdy XY: {self.wynik.dystans_przejazdow:.2f} cm"
            + f"\nLiczba faz ruchu: {len(self.fazy)}"
        )
        self.reset()

    def start(self) -> None:
        if self.indeks_fazy >= len(self.fazy):
            self.reset()
        self.uruchomiony = True
        self.ostatni_czas = time.perf_counter()

    def pauza(self) -> None:
        self.uruchomiony = not self.uruchomiony
        self.ostatni_czas = time.perf_counter()

    def stop(self) -> None:
        self.uruchomiony = False
        self.reset()

    def reset(self) -> None:
        self.uruchomiony = False
        self.indeks_fazy = 0
        self.postep_fazy = 0.0
        self.czas_symulacji = 0.0
        self.slad.clear()
        self.pozycja = self.fazy[0].start if self.fazy else (*map(float, PUNKTY[0]), 0.0)
        self.rysuj()

    def _predkosc(self, faza: Faza) -> float:
        if faza.rodzaj == "roboczy":
            return self.predkosc_pracy.get()
        if faza.rodzaj == "jalowy":
            return self.predkosc_jalowa.get()
        return self.predkosc_z.get()

    def _krok(self) -> None:
        teraz = time.perf_counter()
        dt = min(teraz - self.ostatni_czas, 0.1)
        self.ostatni_czas = teraz
        if self.uruchomiony and self.fazy:
            self.czas_symulacji += dt
            pozostalo = dt
            while pozostalo > 0 and self.indeks_fazy < len(self.fazy):
                faza = self.fazy[self.indeks_fazy]
                czas_fazy = faza.dlugosc / self._predkosc(faza) if faza.dlugosc else 0.0
                brakujacy = czas_fazy * (1.0 - self.postep_fazy)
                if czas_fazy == 0 or pozostalo >= brakujacy:
                    self.pozycja = faza.koniec
                    pozostalo -= brakujacy
                    self.indeks_fazy += 1
                    self.postep_fazy = 0.0
                else:
                    self.postep_fazy += pozostalo / czas_fazy
                    self.pozycja = tuple(
                        a + (b - a) * self.postep_fazy for a, b in zip(faza.start, faza.koniec)
                    )
                    pozostalo = 0.0
            if self.indeks_fazy >= len(self.fazy):
                if self.petla.get():
                    self.indeks_fazy = 0
                    self.postep_fazy = 0.0
                    self.pozycja = self.fazy[0].start
                    self.slad.clear()
                else:
                    self.uruchomiony = False
            rodzaj = self.fazy[min(self.indeks_fazy, len(self.fazy) - 1)].rodzaj
            self.slad.append((self.pozycja[0], self.pozycja[1], rodzaj, self.pozycja[2]))
            if len(self.slad) > 3000:
                self.slad = self.slad[-3000:]
            self._aktualizuj_widok()
        self.root.after(30, self._krok)

    def rysuj(self) -> None:
        if not hasattr(self, "canvas"):
            return
        c = self.canvas
        c.delete("all")

        # Plaszczyzna XY z podzialka 0,5 cm.
        for pol in range(0, 55):
            y = pol / 2
            self._linia3d((0, y, 0), (19, y, 0), "#d5dce2" if pol % 2 else "#aab5bf", 1)
        for pol in range(0, 39):
            x = pol / 2
            self._linia3d((x, 0, 0), (x, 27, 0), "#d5dce2" if pol % 2 else "#aab5bf", 1)

        self._linia3d((0, 0, 0), (20, 0, 0), "#263746", 3, strzalka=True)
        self._linia3d((0, 0, 0), (0, 28, 0), "#263746", 3, strzalka=True)
        self._linia3d((0, 0, 0), (0, 0, max(7.0, self.wysokosc.get() * 1.35)), "#263746", 3, strzalka=True)
        for tekst, punkt in (("X", (20, 0, 0)), ("Y", (0, 28, 0)), ("Z", (0, 0, max(7.0, self.wysokosc.get() * 1.35)))):
            sx, sy, _ = self._projektuj(punkt)
            c.create_text(sx, sy - 10, text=tekst, fill="#263746", font=("Segoe UI", 10, "bold"))

        z_przeszkody = max(6.0, self.wysokosc.get() * 1.2)
        if isinstance(self.przeszkoda, Prostokat):
            r = self.przeszkoda
            dol = [(r.xmin, r.ymin, 0), (r.xmax, r.ymin, 0), (r.xmax, r.ymax, 0), (r.xmin, r.ymax, 0)]
            gora = [(x, y, z_przeszkody) for x, y, _ in dol]
            sciany = [gora] + [[dol[i], dol[(i + 1) % 4], gora[(i + 1) % 4], gora[i]] for i in range(4)]
            for sciana in sorted(sciany, key=lambda s: sum(self._projektuj(p)[2] for p in s) / len(s)):
                self._wielokat3d(sciana, "#ef9a9a", "#8b0000")
            sx, sy, _ = self._projektuj((r.xmin, r.ymax, z_przeszkody))
            c.create_text(sx, sy - 10, text="PRZESZKODA", fill="#8b0000", font=("Segoe UI", 8, "bold"))
        elif isinstance(self.przeszkoda, OdcinekPrzeszkody):
            a, b = self.przeszkoda.a, self.przeszkoda.b
            sciana = [(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], z_przeszkody), (a[0], a[1], z_przeszkody)]
            self._wielokat3d(sciana, "#d96b6b", "#750000")
            sx, sy, _ = self._projektuj((a[0], a[1], z_przeszkody))
            c.create_text(sx, sy - 10, text="PRZESZKODA", fill="#8b0000", font=("Segoe UI", 8, "bold"))

        for faza in self.fazy:
            self._linia3d(
                faza.start,
                faza.koniec,
                self.KOLORY[faza.rodzaj],
                3,
                przerywana=faza.rodzaj == "jalowy",
            )

        for numer, (x, y) in enumerate(PUNKTY, 1):
            sx, sy, _ = self._projektuj((x, y, 0))
            c.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, fill="white", outline="black", width=2)
            c.create_text(sx + 10, sy - 10, text=f"P{numer}", font=("Segoe UI", 8, "bold"))

        x, y, z = self.pozycja
        if self.pokaz_slad.get() and len(self.slad) > 1:
            wspolrzedne = []
            for px, py, _rodzaj, pz in self.slad:
                sx, sy, _ = self._projektuj((px, py, pz))
                wspolrzedne.extend((sx, sy))
            c.create_line(*wspolrzedne, fill="#27ae60", width=2)
        self._linia3d((x, y, 0), (x, y, z), "#27ae60", 2, przerywana=True)
        sx, sy, _ = self._projektuj((x, y, z))
        c.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, fill="#2ecc71", outline="#123524", width=3)
        c.create_text(sx, sy - 18, text=f"Z={z:.2f}", fill="#123524", font=("Segoe UI", 9, "bold"))

        c.create_text(
            12,
            12,
            anchor="nw",
            text="3D: niebieski - praca | pomaranczowy - jalowy | fioletowy - os Z",
            fill="#263746",
            font=("Segoe UI", 9, "bold"),
        )
        self._aktualizuj_status()

    def _aktualizuj_widok(self) -> None:
        self.rysuj()

    def _projektuj(self, punkt: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = punkt
        dx, dy = x - 9.5, y - 13.5
        cos_a, sin_a = math.cos(self.kat_obrotu), math.sin(self.kat_obrotu)
        xr = cos_a * dx - sin_a * dy
        yr = sin_a * dx + cos_a * dy
        szer = max(self.canvas.winfo_width(), 500)
        wys = max(self.canvas.winfo_height(), 500)
        skala = min((szer - 70) / 34.0, (wys - 70) / 25.0) * self.zoom
        sx = szer * 0.47 + xr * skala
        sy = wys * 0.57 - (yr * math.sin(self.kat_widoku) + z * math.cos(self.kat_widoku)) * skala
        glebokosc = yr * math.cos(self.kat_widoku) - z * math.sin(self.kat_widoku)
        return sx, sy, glebokosc

    def _linia3d(
        self,
        a: tuple[float, float, float],
        b: tuple[float, float, float],
        kolor: str,
        szerokosc: int,
        przerywana: bool = False,
        strzalka: bool = False,
    ) -> None:
        x1, y1, _ = self._projektuj(a)
        x2, y2, _ = self._projektuj(b)
        self.canvas.create_line(
            x1,
            y1,
            x2,
            y2,
            fill=kolor,
            width=szerokosc,
            dash=(7, 5) if przerywana else None,
            arrow=tk.LAST if strzalka else tk.NONE,
        )

    def _wielokat3d(self, punkty, wypelnienie: str, obrys: str) -> None:
        ekran = []
        for punkt in punkty:
            x, y, _ = self._projektuj(punkt)
            ekran.extend((x, y))
        self.canvas.create_polygon(*ekran, fill=wypelnienie, outline=obrys, width=2)

    def _aktualizuj_status(self) -> None:
        x, y, z = self.pozycja
        if self.fazy and self.indeks_fazy < len(self.fazy):
            faza = self.fazy[self.indeks_fazy]
            stan = "RUCH" if self.uruchomiony else "PAUZA"
            opis = faza.opis
            nr = self.indeks_fazy + 1
        else:
            stan, opis, nr = "KONIEC", "Trasa zakonczona", len(self.fazy)
        self.status.set(
            f"Stan: {stan}\nFaza: {nr}/{len(self.fazy)} - {opis}\n"
            f"Pozycja: X={x:.2f}, Y={y:.2f}, Z={z:.2f} cm\n"
            f"Czas symulacji: {self.czas_symulacji:.1f} s"
        )

    def pomoc(self) -> None:
        messagebox.showinfo(
            "Pomoc",
            "Niebieski: ruch roboczy przy Z=0.\n"
            "Pomaranczowy: przejazd jalowy omijajacy przeszkode w XY.\n"
            "Fioletowy stan: podnoszenie lub opuszczanie osi Z.\n\n"
            "Obrot sceny: przeciagnij lewym przyciskiem myszy.\n"
            "Powiekszenie: uzyj rolki myszy lub paska narzedzi.\n\n"
            "Zmiana parametrow zaczyna obowiazywac po nacisnieciu "
            "'Zastosuj i przelicz trase'.",
        )


def test_bez_gui() -> None:
    for nazwa in ("Brak", "Prostokat", "Odcinek"):
        przeszkoda = przeszkoda_z_nazwy(nazwa)
        wynik = optymalizuj(przeszkoda)
        fazy = zbuduj_fazy(wynik, przeszkoda, 5.0)
        assert fazy and fazy[0].start[:2] == tuple(map(float, PUNKTY[0]))
        assert all(faza.dlugosc >= 0 for faza in fazy)
        print(
            f"{nazwa}: faz={len(fazy)}, trasa={wynik.dystans_calkowity:.2f} cm, "
            f"kolejnosc={tekst_kolejnosci(wynik)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Sprawdz planowanie bez uruchamiania GUI.")
    parser.add_argument(
        "--przeszkoda",
        choices=("Brak", "Prostokat", "Odcinek"),
        default="Prostokat",
        help="Poczatkowy wariant przeszkody.",
    )
    args = parser.parse_args()
    if args.test:
        test_bez_gui()
        return
    root = tk.Tk()
    Symulator(root, args.przeszkoda)
    root.mainloop()


if __name__ == "__main__":
    main()
