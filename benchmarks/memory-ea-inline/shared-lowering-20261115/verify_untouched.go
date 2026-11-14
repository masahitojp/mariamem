package main
import("go/ast";"go/parser";"go/token";"go/format";"bytes";"os";"fmt")
func funcs(path string)map[string]string{f,e:=parser.ParseFile(token.NewFileSet(),path,nil,0);if e!=nil{panic(e)};m:=map[string]string{};for _,d:=range f.Decls{var b bytes.Buffer;format.Node(&b,token.NewFileSet(),d);name:="";if fn,ok:=d.(*ast.FuncDecl);ok{name=fn.Name.Name}else{name=b.String()};m[name]=b.String()};return m}
func main(){a,b:=funcs(os.Args[1]),funcs(os.Args[2]);if len(a)!=len(b){panic("inventory changed")};n:=0;for k,v:=range a{if k==os.Args[3]{if v==b[k]{panic("unchanged target")};continue};if v!=b[k]{panic("unexpected change "+k)};n++};fmt.Println("unchanged declarations",n)}
