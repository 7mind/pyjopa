public class TestCasting {
    public static void main(String[] args) {
        int i = 100;
        long l = i;
        double d = l;
        int i2 = (int)d;
        System.out.println(l);
        System.out.println(i2);
    }
}
