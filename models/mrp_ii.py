# -*- coding: utf-8 -*-
###############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2017 Humanytek (<www.humanytek.com>).
#    Rubén Bravo <rubenred18@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)


class MrpIi(models.TransientModel):
    _name = "mrp.ii"

    @api.multi
    def calculate(self):
        MrpBom = self.env['mrp.bom']
        BillMaterialIi = self.env['bill.material.ii']
        BillMaterialIiSale = self.env['bill.material.ii.sale']
        BillMaterialIiPurchase = self.env['bill.material.ii.purchase']
        ProductCompromise = self.env['product.compromise']
        StockMove = self.env['stock.move']
        BillMaterialIi.search([]).unlink()
        #BUSCAR POR LISTA DE MATERIALES
        #mrp_boms = MrpBom.search([
                        #('product_tmpl_id.id', '=', self.product_id.id)])

        #for mrp_bom in mrp_boms:
        if self.bom_id:
            for line in self.bom_id.bom_line_ids:
                bill_id = BillMaterialIi.create({
                            'product_id': line.product_id.id,
                            'mrp_ii_id': self.id,
                            'qty_product': self.qty_product * line.product_qty})
                #REVISAR SI AQUI SE PUEDE BUSCAR POR UBICACION, AUN NO SE SI SEA ORIGEN O DESTINO
                stock_moves = StockMove.search([
                                ('product_id.id', '=', line.product_id.id),
                                ('state', 'in', ('assigned', 'confirmed')),
                                ('raw_material_production_id', '!=', False),
                                '|',
                                ('location_id', '=', self.location_id.id),
                                ('location_dest_id', '=', self.location_id.id)
                                ])
                for move in stock_moves:
                    BillMaterialIiSale.create({
                                'bill_material_ii_id': bill_id.id,
                                'move_id': move.id})

                    product_compromises = ProductCompromise.search([
                                    ('product_id.id', '=', line.product_id.id),
                                    ('state', '=', 'assigned'),
                                    ('stock_move_out_id', '=', move.id)])
                    for product_compromise in product_compromises:
                        BillMaterialIiPurchase.create({
                            'bill_material_ii_id': bill_id.id,
                            'move_id': move.id,
                            'move_in_id': product_compromise.stock_move_in_id.id})

        return {
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.ii',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'new',
                }

    @api.model
    def _get_default_location_id(self):
        StockLocation = self.env['stock.location']
        stock_locations = StockLocation.search([('name', '=', 'Existencias'),
                                        ('location_id.name', '=', 'WH/1')])
        if stock_locations:
            return stock_locations[0].id
        else:
            return False

        #location = self.env.ref('stock.stock_location_stock',
                                #raise_if_not_found=False)
        #return location and location.id or False

    @api.multi
    @api.onchange('product_id')
    def onchange_product_id(self):
        MrpBom = self.env['mrp.bom']
        mrp_boms = MrpBom.search([
            ('product_tmpl_id.id', '=', self.product_id.id)])
        if mrp_boms:
            self.bom_id = mrp_boms[0].id
        return {}

    product_id = fields.Many2one('product.template', 'Product', required=True)
    qty_product = fields.Float('Quantity', required=True, default=1)
    bill_material_ii_ids = fields.One2many('bill.material.ii',
                            'mrp_ii_id',
                            'BoM')
    location_id = fields.Many2one('stock.location', 'Location', required=True,
                                default=_get_default_location_id)
    bom_id = fields.Many2one('mrp.bom', 'BOM', required=True, )


class BillMaterialIi(models.TransientModel):
    _name = "bill.material.ii"

    mrp_ii_id = fields.Many2one('mrp.ii', 'MRP II')
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    qty_product = fields.Float('Quantity', readonly=True)
    bill_material_ii_sale_ids = fields.One2many('bill.material.ii.sale',
                            'bill_material_ii_id',
                            'BoM-Sale', readonly=True)
    bill_material_ii_purchase_ids = fields.One2many('bill.material.ii.purchase',
                            'bill_material_ii_id',
                            'BoM-Purchase', readonly=True)
    #product_qty_product = fields.Float(related='product_id.qty_available',
                            #string='Total Product', readonly=True, store=False)
    product_qty_product = fields.Float('Total Product',
                            compute='_compute_product_qty_product',
                            readonly=True, store=False)

    #product_incoming_qty = fields.Float(related='product_id.incoming_qty',
                            #string='Total Incoming Product', readonly=True,
                            #store=False)

    product_incoming_qty = fields.Float('Total Incoming Product',
                            compute='_compute_product_incoming_qty',
                            readonly=True, store=False)

    total_compromise_product = fields.Float('Total Compromise Product',
                            compute='_compute_total_compromise_product',
                            readonly=True, store=False)

    total_reserved_product = fields.Float('Total Reserved Product',
                            compute='_compute_total_reserved_product',
                            readonly=True, store=False)

    dis_product_in = fields.Float('Availability Incoming Product',
                            compute='_compute_dis_product_in',
                            readonly=True, store=False)

    dis_product = fields.Float('Availability Product',
                            compute='_compute_dis_product',
                            readonly=True, store=False)

    @api.one
    def _compute_total_compromise_product(self):
        StockMove = self.env['stock.move']
        ProductCompromise = self.env['product.compromise']
        stock_moves = StockMove.search([
                                    ('product_id.id', '=', self.product_id.id),
                                    ('picking_type_id.code', '=', 'incoming'),
                                    ('state', 'not in', ['cancel', 'done']),
                                    ('location_dest_id', '=',
                                        self.mrp_ii_id.location_id.id)])
        qty = 0
        for move in stock_moves:
            product_compromises = ProductCompromise.search([
                                    ('product_id.id', '=', self.product_id.id),
                                    ('state', '=', 'assigned'),
                                    ('stock_move_in_id', '=', move.id)])
            for product_compromise in product_compromises:
                qty += product_compromise.qty_compromise
            #self.total_compromise_product = sum([product_compromise.qty_compromise
                                #for product_compromise in
                                #product_compromises])
        self.total_compromise_product = qty

    @api.one
    def _compute_total_reserved_product(self):
        StockMove = self.env['stock.move']
        stock_moves = StockMove.search([
                                    ('product_id.id', '=', self.product_id.id),
                                    ('state', 'in', ('assigned', 'confirmed')),
                                    ('location_id', '=',
                                        self.mrp_ii_id.location_id.id)])
        self.total_reserved_product = sum([stock_move.reserved_availability
                                for stock_move in
                                stock_moves])

    @api.one
    def _compute_product_qty_product(self):
        StockQuant = self.env['stock.quant']
        #StockMove = self.env['stock.move']
        stock_quants = StockQuant.search([
                                    ('product_id.id', '=', self.product_id.id),
                                    ('location_id', '=',
                                        self.mrp_ii_id.location_id.id)])
        self.product_qty_product = sum([stock_quant.quantity
                                for stock_quant in
                                stock_quants])

    @api.one
    def _compute_product_incoming_qty(self):
        StockMove = self.env['stock.move']
        stock_moves = StockMove.search([
                                    ('product_id.id', '=', self.product_id.id),
                                    ('picking_type_id.code', '=', 'incoming'),
                                    ('state', 'not in', ['cancel', 'done']),
                                    ('location_dest_id', '=',
                                        self.mrp_ii_id.location_id.id)])
        self.product_incoming_qty = sum([stock_move.product_uom_qty
                                for stock_move in
                                stock_moves])

    @api.one
    def _compute_dis_product_in(self):
        self.dis_product_in = self.product_incoming_qty - self.total_compromise_product

    @api.one
    def _compute_dis_product(self):
        self.dis_product = self.product_qty_product - self.total_reserved_product


class BillMaterialIiSale(models.TransientModel):
    _name = "bill.material.ii.sale"

    bill_material_ii_id = fields.Many2one('bill.material.ii', 'MRP II')
    move_id = fields.Many2one('stock.move', 'Move', required=True)
    product_qty = fields.Float(related='move_id.product_uom_qty',
                          string='Quantity', readonly=True, store=False)
    product_reserved_qty = fields.Float(related='move_id.reserved_availability',
                          string='Quantity Reserved',
                          readonly=True, store=False)
    sale_id = fields.Many2one(
                        related='move_id.raw_material_production_id.sale_id',
                        string='Sale Order', readonly=True, store=False)
    partner_id = fields.Many2one(
                        related='move_id.raw_material_production_id.partner_id',
                        string='Customer', readonly=True, store=False)


class BillMaterialIiPurchase(models.TransientModel):
    _name = "bill.material.ii.purchase"

    bill_material_ii_id = fields.Many2one('bill.material.ii', 'MRP II')
    move_id = fields.Many2one('stock.move', 'Move', required=True)
    move_in_id = fields.Many2one('stock.move', 'Move In', required=True)

    product_qty = fields.Float(related='move_id.product_uom_qty',
                          string='Quantity', readonly=True, store=False)
    #product_reserved_qty = fields.Float(related='move_id.reserved_availability',
                          #string='Quantity Reserved',
                          #readonly=True, store=False)
    sale_id = fields.Many2one(
                        related='move_id.raw_material_production_id.sale_id',
                        string='Sale Order', readonly=True, store=False)
    partner_id = fields.Many2one(
                        related='move_id.raw_material_production_id.partner_id',
                        string='Customer', readonly=True, store=False)
    compromise_product = fields.Float('Compromise Product',
                            compute='_compute_compromise_product',
                            readonly=True, store=False)
    picking_purchase_order = fields.Char(
                                related='move_in_id.picking_id.origin',
                                string='Purchase Order',
                                readonly=True, store=False)

    @api.one
    def _compute_compromise_product(self):
        ProductCompromise = self.env['product.compromise']
        product_compromises = ProductCompromise.search([
                        ('product_id.id', '=', self.move_in_id.product_id.id),
                        ('state', '=', 'assigned'),
                        ('stock_move_in_id', '=', self.move_in_id.id),
                        ('stock_move_out_id', '=', self.move_id.id),
                        ])
        self.compromise_product = sum([product_compromise.qty_compromise
                                for product_compromise in
                                product_compromises])