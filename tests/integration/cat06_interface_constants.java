interface Constants {
    int MAX = 100;
    int MIN = 0;
}

public class TestInterfaceConstants implements Constants {
    public static void main(String[] args) {
        System.out.println(MAX);
        System.out.println(MIN);
        System.out.println(Constants.MAX);
    }
}