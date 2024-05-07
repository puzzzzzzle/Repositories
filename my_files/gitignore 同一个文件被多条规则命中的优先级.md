- 在 .gitignore 文件中，可以设置多条规则来匹配不同的文件或文件夹。如果同一个文件被多条规则命中，那么 Git 会根据这些规则的优先级来决定是否忽略该文件。
- 优先级规则如下：
  - 优先级最高的是明确指定的文件或文件夹路径。例如，/file.txt 会明确匹配根目录下的 file.txt 文件。
  - 如果一个文件同时被多条模式匹配，那么 Git 会根据 .gitignore 文件中规则的顺序来决定优先级。在 .gitignore 文件中，越靠近底部的规则优先级越高。
  - 如果一个文件被多条模式匹配，但其中有一条是以 "!" 开头的（表示不忽略该文件），那么该文件将不会被忽略。例如：
    ```
    # .gitignore 文件内容
    *.txt
    !important.txt
    important.txt
    ```
    - 在这个例子中，尽管 important.txt 文件同时被 *.txt 和 important.txt 规则匹配，但是 !important.txt 规则会将其排除在外，所以该文件不会被忽略。
- 参考 https://git-scm.com/docs/gitignore