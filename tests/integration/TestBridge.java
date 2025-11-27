class Box<T> {
    T value;

    void set(T v) {
        value = v;
    }

    T get() {
        return value;
    }
}

class StringBox extends Box<String> {
    @Override
    void set(String v) {
        super.set(v);
    }

    @Override
    String get() {
        return super.get();
    }
}

public class TestBridge {
    public static void main(String[] args) {
        StringBox box = new StringBox();
        box.set("hello");
        System.out.println(box.get());

        // Test polymorphism - call through supertype reference
        Box<String> genericBox = box;
        genericBox.set("world");
        System.out.println(genericBox.get());
    }
}
