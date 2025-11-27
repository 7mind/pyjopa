final class FinalClass {
    int value = 123;
}

public class TestFinalClass {
    public static void main(String[] args) {
        FinalClass obj = new FinalClass();
        System.out.println(obj.value);
    }
}