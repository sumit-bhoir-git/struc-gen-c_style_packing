package structag

import "github.com/dave/jennifer/jen"

type Context struct {
	checkBound    *jen.Statement
	staticBitPos  int
	dynamicBitPos *jen.Statement
	// Pack directive: 0 = natural, >0 = pack bytes (e.g., 1,2,4)
    Pack int
}

// inserts a new Null CheckBound statement placeholder
// moves the global checkBound pointer to the new placeholder statement
// returns the placeholder
func (c *Context) insertNewCheckBound() *jen.Statement {
	newCheckBound := jen.Null()
	c.checkBound = newCheckBound
	return jen.Line().Add(newCheckBound)
}

// flush the content of context state into "m" variable
// after flush "m" points to the next free byte-aligned position and
// the context is empty again (static + dynamic bit positions)
func (c *Context) Flush() *jen.Statement {
	    // Build expression representing total pending bits (static + dynamic)
    var bitExpr *jen.Statement
    if c.dynamicBitPos != nil {
        bitExpr = jen.Parens(jen.Lit(c.staticBitPos).Op("+").Add(c.dynamicBitPos.Clone()))
    } else {
        bitExpr = jen.Parens(jen.Lit(c.staticBitPos))
    }

    // reset context state now (compile-time state consumed)
    c.staticBitPos = 0
    c.dynamicBitPos = nil

    // Generate code:
    // advance m by whole bytes in bitExpr: m += bitExpr / 8
    // if remainder bits exist: m++
    // then apply packing alignment: if Pack>0 and m%Pack !=0 then m += Pack - (m%Pack)
    stmt := jen.Null()

    // m += bitExpr / 8
    stmt.Add(jen.Id("m").Op("+=").Add(bitExpr.Clone().Op("/").Lit(8))).Line()

    // if bitExpr % 8 != 0 { m++ }
    stmt.If(bitExpr.Clone().Op("%").Lit(8).Op("!=").Lit(0)).Block(
        jen.Id("m").Op("++"),
    ).Line()

    // apply pack alignment at runtime if requested
    if c.Pack > 0 {
        // if m % Pack != 0 { m += Pack - (m % Pack) }
        stmt.If(jen.Id("m").Op("%").Lit(c.Pack).Op("!=").Lit(0)).Block(
            jen.Id("m").Op("+=").Parens(jen.Lit(c.Pack).Op("-").Parens(jen.Id("m").Op("%").Lit(c.Pack))),
        ).Line()
    }

    // attach a new checkBound placeholder and return
    stmt.Add(c.insertNewCheckBound())
    return stmt
}
