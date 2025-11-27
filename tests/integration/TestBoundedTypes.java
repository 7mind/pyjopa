class Pair<T extends Number> {
    T first;
    T second;

    Pair(T f, T s) {
        first = f;
        second = s;
    }

    T getFirst() {
        return first;
    }

    T getSecond() {
        return second;
    }
}

public class TestBoundedTypes {
    public static void main(String[] args) {
        Pair<Integer> intPair = new Pair<Integer>(10, 20);
        Number n1 = intPair.getFirst();
        Number n2 = intPair.getSecond();
        System.out.println(n1);
        System.out.println(n2);
    }
}
