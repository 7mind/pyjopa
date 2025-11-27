class VarArgsTest {
    static int sum(int... numbers) {
        int total = 0;
        for (int n : numbers) {
            total += n;
        }
        return total;
    }
}

public class TestVarargs {
    public static void main(String[] args) {
        System.out.println(VarArgsTest.sum(1, 2, 3));
        System.out.println(VarArgsTest.sum(10, 20));
    }
}