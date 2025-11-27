public class Outer {
    static class Inner {
        int value;

        Inner(int v) {
            value = v;
        }

        int getValue() {
            return value;
        }
    }

    public static void main(String[] args) {
        Outer.Inner inner = new Outer.Inner(42);
        System.out.println(inner.getValue());
    }
}
