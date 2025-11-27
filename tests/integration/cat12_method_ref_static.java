import java.util.function.Function;

public class TestMethodRefStatic {
    public static int doubleIt(int x) {
        return x * 2;
    }

    public static void main(String[] args) {
        Function<Integer, Integer> f = TestMethodRefStatic::doubleIt;
        System.out.println(f.apply(5));
    }
}
