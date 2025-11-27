public class TestArrayObjects {
    public static void main(String[] args) {
        String[] words = new String[3];
        words[0] = "Hello";
        words[1] = "World";
        words[2] = "!";
        for (String w : words) {
            System.out.println(w);
        }
    }
}