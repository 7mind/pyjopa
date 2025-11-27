public class TestMultipleCatch {
    public static void main(String[] args) {
        try {
            int[] arr = new int[2];
            arr[5] = 10;
        } catch (ArrayIndexOutOfBoundsException e) {
            System.out.println("Array error");
        } catch (Exception e) {
            System.out.println("Other error");
        }
    }
}