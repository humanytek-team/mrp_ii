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
        BillMaterialIi.search([]).unlink()
        mrp_boms = MrpBom.search([
                        ('product_tmpl_id.id', '=', self.product_id.id)])
        for mrp_bom in mrp_boms:
            for line in mrp_bom.bom_line_ids:
                BillMaterialIi.create({'product_id': line.product_id.id,
                            'mrp_ii_id': self.id,
                            'qty_product': self.qty_product * line.product_qty})
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.ii',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'new',
                }

    product_id = fields.Many2one('product.template', 'Product', required=True)
    qty_product = fields.Float('Quantity', required=True, default=1)
    bill_material_ii_ids = fields.One2many('bill.material.ii',
                            'mrp_ii_id',
                            'BoM')


class BillMaterialIi(models.TransientModel):
    _name = "bill.material.ii"

    mrp_ii_id = fields.Many2one('mrp.ii', 'MRP II')
    product_id = fields.Many2one('product.product', 'Product')
    qty_product = fields.Float('Quantity')
    product_qty_product = fields.Float(related='product_id.qty_available',
                            string='Total Product', readonly=True, store=False)

    product_incoming_qty = fields.Float(related='product_id.incoming_qty',
                            string='Total Incoming Product', readonly=True,
                            store=False)

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
        ProductCompromise = self.env['product.compromise']
        product_compromises = ProductCompromise.search([
                                    ('product_id.id', '=', self.product_id.id),
                                    ('state', '=', 'assigned')])

        self.total_compromise_product = sum([product_compromise.qty_compromise
                                for product_compromise in
                                product_compromises])

    @api.one
    def _compute_total_reserved_product(self):
        StockMove = self.env['stock.move']
        stock_moves = StockMove.search([
                                    ('product_id.id', '=', self.product_id.id),
                                    ('state', 'in', ('assigned', 'confirmed'))])
        self.total_reserved_product = sum([stock_move.reserved_availability
                                for stock_move in
                                stock_moves])

    @api.one
    def _compute_dis_product_in(self):
        self.dis_product_in = self.product_incoming_qty - self.total_compromise_product

    @api.one
    def _compute_dis_product(self):
        self.dis_product = self.product_qty_product - self.total_reserved_product
