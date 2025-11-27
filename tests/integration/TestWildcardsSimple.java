class Container<T> {
    T value;

    T get() {
        return value;
    }

    void set(T v) {
        value = v;
    }
}

public class TestWildcardsSimple {
    // Upper bounded wildcard
    public static Number getFromContainer(Container<? extends Number> c) {
        return c.get();
    }

    // Unbounded wildcard
    public static Object getFromAny(Container<?> c) {
        return c.get();
    }

    public static void main(String[] args) {
        Container<Integer> intContainer = new Container<Integer>();
        intContainer.set(42);

        Number n = getFromContainer(intContainer);
        System.out.println(n);

        Object obj = getFromAny(intContainer);
        System.out.println(obj);
    }
}
