class Helper {
    public int publicField = 1;
    private int privateField = 2;
    protected int protectedField = 3;

    public int getPrivate() {
        return privateField;
    }
}

public class TestAccessModifiers {
    public static void main(String[] args) {
        Helper h = new Helper();
        System.out.println(h.publicField);
        System.out.println(h.getPrivate());
        System.out.println(h.protectedField);
    }
}