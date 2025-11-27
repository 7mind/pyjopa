enum Color {
    RED, GREEN, BLUE
}

public class TestEnum {
    public static void main(String[] args) {
        Color c = Color.RED;
        System.out.println(c);
        System.out.println(c.ordinal());
    }
}
