import java.util.function.Supplier;

public class TestLambdaCapture {
    public static void main(String[] args) {
        int x = 42;
        Supplier<Integer> supplier = () -> x + 10;
        System.out.println(supplier.get());
    }
}
