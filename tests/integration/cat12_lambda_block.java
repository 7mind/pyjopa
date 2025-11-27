import java.util.function.Consumer;

public class TestLambdaBlock {
    public static void main(String[] args) {
        Consumer<String> printer = s -> {
            System.out.println("Value: " + s);
            System.out.println("Length: " + s.length());
        };
        printer.accept("Hello");
    }
}
