# Copyright 2019 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class StockDemandEstimateSheet(models.TransientModel):
    _name = "stock.demand.estimate.sheet"
    _description = "Stock Demand Estimate Sheet"

    date_start = fields.Date(
        string="Date From",
        readonly=True,
    )
    date_end = fields.Date(
        string="Date to",
        readonly=True,
    )
    date_range_type_id = fields.Many2one(
        string="Date Range Type",
        comodel_name="date.range.type",
        readonly=True,
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        readonly=True,
    )
    line_ids = fields.Many2many(
        string="Estimates",
        comodel_name="stock.demand.estimate.sheet.line",
        relation="stock_demand_estimate_line_rel",
    )
    product_ids = fields.Many2many(
        string="Products",
        comodel_name="product.product",
    )

    @api.onchange(
        "date_start",
        "date_end",
        "date_range_type_id",
    )
    def _onchange_dates(self):
        for sheet in self:
            if not all([sheet.date_start, sheet.date_end, sheet.date_range_type_id]):
                return
            ranges = sheet._get_ranges()
            if not ranges:
                raise UserError(_("There is no ranges created."))
            estimates = self.env["stock.demand.estimate"].search(
                [
                    ("product_id", "in", sheet.product_ids.ids),
                    ("date_range_id", "in", ranges.ids),
                    ("location_id", "=", sheet.location_id.id),
                ]
            )
            lines = []
            for product in sheet.product_ids:
                for _range in ranges:
                    estimate = estimates.filtered(
                        lambda x, _range=_range, product=product: (
                            x.date_range_id == _range and x.product_id == product
                        )
                    )
                    if estimate:
                        uom_id = fields.first(estimate).product_uom.id
                        uom_qty = estimate[0].product_uom_qty
                        estimate_id = estimate[0].id
                    else:
                        uom_id = product.uom_id.id
                        uom_qty = 0.0
                        estimate_id = None
                    lines.append(
                        (
                            0,
                            0,
                            sheet._get_default_estimate_line(
                                _range,
                                product,
                                uom_id,
                                uom_qty,
                                estimate_id=estimate_id,
                            ),
                        )
                    )
            sheet.line_ids = lines

    def _get_ranges(self):
        domain_1 = [
            "&",
            ("type_id", "=", self.date_range_type_id.id),
            "|",
            "&",
            ("date_start", ">=", self.date_start),
            ("date_start", "<=", self.date_end),
            "&",
            ("date_end", ">=", self.date_start),
            ("date_end", "<=", self.date_end),
        ]
        domain_2 = [
            "&",
            ("type_id", "=", self.date_range_type_id.id),
            "&",
            ("date_start", "<=", self.date_start),
            ("date_end", ">=", self.date_start),
        ]
        domain = expression.OR([domain_1, domain_2])
        ranges = self.env["date.range"].search(domain)
        return ranges

    def _get_default_estimate_line(
        self, _range, product, uom_id, uom_qty, estimate_id=None
    ):
        name_y = f"{product.name} - {product.uom_id.name}"
        if product.default_code:
            name_y += f"[{product.default_code}] {name_y}"
        values = {
            "value_x": _range.name,
            "value_y": name_y,
            "date_range_id": _range.id,
            "product_id": product.id,
            "product_uom": uom_id,
            "product_uom_qty": uom_qty,
            "location_id": self.location_id.id,
            "estimate_id": estimate_id,
        }
        return values

    @api.model
    def _prepare_estimate_data(self, line):
        return {
            "date_range_id": line.date_range_id.id,
            "product_id": line.product_id.id,
            "location_id": line.location_id.id,
            "product_uom_qty": line.product_uom_qty,
            "product_uom": line.product_id.uom_id.id,
        }

    def button_validate(self):
        res = []
        for line in self.line_ids:
            if line.estimate_id:
                line.estimate_id.product_uom_qty = line.product_uom_qty
                res.append(line.estimate_id.id)
            else:
                data = self._prepare_estimate_data(line)
                estimate = self.env["stock.demand.estimate"].create(data)
                res.append(estimate.id)
        res = {
            "domain": [("id", "in", res)],
            "name": _("Stock Demand Estimates"),
            "src_model": "stock.demand.estimate.wizard",
            "view_type": "form",
            "view_mode": "tree",
            "res_model": "stock.demand.estimate",
            "type": "ir.actions.act_window",
        }
        return res
