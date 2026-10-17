import java.math.BigInteger;
import java.util.*;

/** Minimal strict JSON for exact integer certificates; no external dependencies. */
final class Json {
    static String write(Object value) {
        StringBuilder s = new StringBuilder(); append(s, value, 0); return s.append('\n').toString();
    }
    private static void append(StringBuilder s, Object v, int depth) {
        if (v == null) s.append("null");
        else if (v instanceof String text) quote(s, text);
        else if (v instanceof Boolean || v instanceof Number) s.append(v);
        else if (v instanceof Map<?,?> map) {
            s.append('{'); int i = 0;
            for (var entry : map.entrySet()) {
                if (i++ != 0) s.append(',');
                s.append('\n').append("  ".repeat(depth + 1)); quote(s, entry.getKey().toString()); s.append(": ");
                append(s, entry.getValue(), depth + 1);
            }
            if (!map.isEmpty()) s.append('\n').append("  ".repeat(depth)); s.append('}');
        } else if (v instanceof List<?> list) {
            s.append('['); int i = 0;
            for (Object item : list) { if (i++ != 0) s.append(','); append(s, item, depth); }
            s.append(']');
        } else throw new IllegalArgumentException("Unsupported JSON value " + v.getClass());
    }
    private static void quote(StringBuilder s, String text) {
        s.append('"');
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            switch (c) {
                case '"' -> s.append("\\\""); case '\\' -> s.append("\\\\");
                case '\n' -> s.append("\\n"); case '\r' -> s.append("\\r"); case '\t' -> s.append("\\t");
                default -> { if (c < 32) s.append(String.format(Locale.ROOT, "\\u%04x", (int)c)); else s.append(c); }
            }
        }
        s.append('"');
    }
    static Map<String,Object> object(Object... pairs) {
        Map<String,Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String)pairs[i], pairs[i + 1]);
        return result;
    }
    static boolean equal(Object a, Object b) {
        if (a instanceof Number && b instanceof Number) return new BigInteger(a.toString()).equals(new BigInteger(b.toString()));
        if (a instanceof Map<?,?> x && b instanceof Map<?,?> y) {
            if (!x.keySet().equals(y.keySet())) return false;
            for (Object k : x.keySet()) if (!equal(x.get(k), y.get(k))) return false;
            return true;
        }
        if (a instanceof List<?> x && b instanceof List<?> y) {
            if (x.size() != y.size()) return false;
            for (int i = 0; i < x.size(); i++) if (!equal(x.get(i), y.get(i))) return false;
            return true;
        }
        return Objects.equals(a, b);
    }
    static Object parse(String text) { return new Parser(text).parse(); }
    private static final class Parser {
        final String text; int i;
        Parser(String text) { this.text = text; }
        IllegalArgumentException error() { return new IllegalArgumentException("Malformed certificate JSON at character " + i); }
        void space() { while (i < text.length() && " \n\r\t".indexOf(text.charAt(i)) >= 0) i++; }
        boolean take(char c) { space(); if (i < text.length() && text.charAt(i) == c) { i++; return true; } return false; }
        void need(char c) { if (!take(c)) throw error(); }
        Object parse() { Object v = value(0); space(); if (i != text.length()) throw error(); return v; }
        Object value(int depth) {
            if (depth > 32) throw error(); space(); if (i == text.length()) throw error();
            char c = text.charAt(i);
            if (c == '"') return string();
            if (take('{')) {
                Map<String,Object> map = new LinkedHashMap<>(); if (take('}')) return map;
                do { space(); String key = string(); need(':'); if (map.containsKey(key)) throw error(); map.put(key, value(depth + 1)); } while (take(','));
                need('}'); return map;
            }
            if (take('[')) { List<Object> list = new ArrayList<>(); if (take(']')) return list;
                do { list.add(value(depth + 1)); } while (take(',')); need(']'); return list; }
            for (String literal : List.of("true", "false", "null")) if (text.startsWith(literal, i)) {
                i += literal.length(); return literal.equals("null") ? null : Boolean.valueOf(literal);
            }
            int start = i; if (c == '-') i++;
            if (i == text.length() || text.charAt(i) < '0' || text.charAt(i) > '9') throw error();
            if (text.charAt(i) == '0') i++;
            else while (i < text.length() && text.charAt(i) >= '0' && text.charAt(i) <= '9') i++;
            return new BigInteger(text.substring(start, i));
        }
        String string() {
            if (i == text.length() || text.charAt(i++) != '"') throw error(); StringBuilder s = new StringBuilder();
            while (i < text.length()) {
                char c = text.charAt(i++); if (c == '"') return s.toString(); if (c < 32) throw error();
                if (c != '\\') { s.append(c); continue; }
                if (i == text.length()) throw error(); c = text.charAt(i++);
                switch (c) {
                    case '"', '\\', '/' -> s.append(c); case 'b' -> s.append('\b'); case 'f' -> s.append('\f');
                    case 'n' -> s.append('\n'); case 'r' -> s.append('\r'); case 't' -> s.append('\t');
                    case 'u' -> { if (i + 4 > text.length()) throw error();
                        try { s.append((char)Integer.parseInt(text.substring(i, i + 4), 16)); }
                        catch (NumberFormatException bad) { throw error(); } i += 4; }
                    default -> throw error();
                }
            }
            throw error();
        }
    }
}
