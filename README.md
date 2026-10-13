# Planowanie trajektorii manipulatora

Projekt pomocniczy do planowania i wizualizacji trasy koncowki manipulatora
KUKA lub ABB. Zawiera punkty robocze, szesc odcinkow procesu, optymalizacje
kolejnosci przejazdu oraz dwa warianty przeszkody: prostokat i odcinek.

## Zawartosc

- `generuj_siatke_a4.py` - generuje dwa arkusze A4 z siatka 1 cm / 0,5 cm;
- `optymalizuj_trajektorie.py` - wyznacza optymalna kolejnosc odcinkow i objazdy;
- `symulator_manipulatora.py` - interaktywny emulator 3D koncowki manipulatora;
- `output/pdf/` - gotowe arkusze i raporty PDF.

## Instalacja

Wymagany jest Python 3.10 lub nowszy. Tkinter jest czescia standardowej
instalacji Pythona w systemie Windows.

```powershell
python -m pip install -r requirements.txt
```

## Emulator 3D

```powershell
python symulator_manipulatora.py
```

Sterowanie widokiem:

- lewy przycisk myszy i przeciagniecie - obrot sceny;
- rolka myszy - przyblizanie i oddalanie;
- `F5` - start;
- `Spacja` - pauza lub wznowienie;
- `Esc` - stop;
- `Ctrl+R` - reset.

Panel pozwala ustawic predkosc pracy, predkosc przejazdu jalowego, predkosc
osi Z, wysokosc podnoszenia oraz typ przeszkody. Przeszkoda jest zawsze
omijana w plaszczyznie XY - podniesienie osi Z nie sluzy do przelotu nad nia.

Test planowania bez uruchamiania okna:

```powershell
python symulator_manipulatora.py --test
```

## Generowanie dokumentow

```powershell
python generuj_siatke_a4.py
python optymalizuj_trajektorie.py --typ-przeszkody prostokat
python optymalizuj_trajektorie.py --typ-przeszkody odcinek `
  --output output/pdf/optymalizacja_trajektorii_odcinek_a4.pdf
```

Przy drukowaniu arkuszy A4 nalezy wybrac skale 100% i wylaczyc dopasowanie
do strony.

