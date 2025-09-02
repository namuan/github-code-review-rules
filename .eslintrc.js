module.exports = {
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: ["eslint:recommended"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
  },
  plugins: ["@typescript-eslint"],
  rules: {
    // Add custom rules here
    "no-unused-vars": "warn",
    "no-console": "off",
  },
  ignorePatterns: ["node_modules/", "dist/", "build/"],
};
