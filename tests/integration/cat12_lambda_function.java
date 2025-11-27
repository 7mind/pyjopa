import java.util.function.Function;

public class TestLambdaFunction {
    public static void main(String[] args) {
        Function<Integer, Integer> doubler = x -> x * 2;
        System.out.println(doubler.apply(5));
        System.out.println(doubler.apply(10));
    }
}
