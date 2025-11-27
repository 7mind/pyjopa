class Test {
    static void riskyMethod() throws Exception {
        throw new Exception("Error");
    }
}

public class TestThrows {
    public static void main(String[] args) {
        try {
            Test.riskyMethod();
        } catch (Exception e) {
            System.out.println("Handled");
        }
    }
}