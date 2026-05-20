def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Nolga bo'lish mumkin emas!")
    return a / b

def get_number(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Iltimos, to'g'ri son kiriting.")

def main():
    operations = {
        '1': ('+', add),
        '2': ('-', subtract),
        '3': ('*', multiply),
        '4': ('/', divide),
    }

    print("=" * 30)
    print("   Python Kalkulyator")
    print("=" * 30)

    while True:
        print("\nAmallar:")
        print("  1. Qo'shish (+)")
        print("  2. Ayirish  (-)")
        print("  3. Ko'paytirish (*)")
        print("  4. Bo'lish  (/)")
        print("  0. Chiqish")

        choice = input("\nAmalni tanlang (0-4): ").strip()

        if choice == '0':
            print("Xayr!")
            break

        if choice not in operations:
            print("Noto'g'ri tanlov. Qaytadan urinib ko'ring.")
            continue

        symbol, operation = operations[choice]

        a = get_number("Birinchi son: ")
        b = get_number("Ikkinchi son: ")

        try:
            result = operation(a, b)
            print(f"\nNatija: {a} {symbol} {b} = {result}")
        except ValueError as e:
            print(f"Xato: {e}")

if __name__ == "__main__":
    main()
